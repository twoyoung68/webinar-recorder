import os
import firebase_admin
from firebase_admin import credentials, storage
from supabase import create_client
import json
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright

# [1. Firebase 인증 로직]
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_json:
        try:
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
            print("✅ Firebase: 환경 변수를 통해 인증되었습니다.")
        except Exception as e:
            print(f"❌ Firebase: 환경 변수 파싱 실패: {e}")
            cred = None
    else:
        # 환경 변수가 없으면 로컬 파일 확인
        json_path = os.path.join(os.path.dirname(__file__), 'firebase_key.json')
        if os.path.exists(json_path):
            cred = credentials.Certificate(json_path)
            print("✅ Firebase: firebase_key.json 파일을 통해 인증되었습니다.")
        else:
            print("⚠️ Firebase: 인증 정보(환경 변수 또는 파일)를 찾을 수 없습니다.")
            cred = None
    
    if cred:
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'webinar-recorder.firebasestorage.app'
        })

# [2. Supabase 설정 및 방어적 로드]
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

supabase = None
if not supabase_url or not supabase_key:
    print("❌ 에러: Supabase 환경 변수가 누락되었습니다!")
    print(f"   - SUPABASE_URL: {'O' if supabase_url else 'X (Missing)'}")
    print(f"   - SUPABASE_KEY: {'O' if supabase_key else 'X (Missing)'}")
else:
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("✅ Supabase: 클라이언트 생성 성공")
    except Exception as e:
        print(f"❌ Supabase: 연결 중 오류 발생: {e}")

# Firebase Storage 버킷 참조
bucket = storage.bucket()

def run_recorder():
    # 시동 전 체크
    if supabase is None:
        print("🛑 Supabase 클라이언트가 설정되지 않아 작업을 중단합니다.")
        return

    print("🔎 녹화 대상 확인 중...")
    now_utc = datetime.now(pytz.utc).isoformat()
    
    try:
        # Supabase에서 예약된 작업 가져오기
        res = supabase.table("webinar_reservations")\
            .select("*")\
            .lt("scheduled_at", now_utc)\
            .in_("status", ["pending", "trigger"])\
            .execute()
        
        jobs = res.data
        if not jobs:
            print("✅ 현재 실행할 예약 작업이 없습니다.")
            return

        for job in jobs:
            job_id = job['id']
            url = job['webinar_url']
            duration = job['duration_min']
            
            print(f"🎬 녹화 시작: {url} ({duration}분)")
            # 상태 업데이트: running
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job_id).execute()
            
            # 영상 파일명 정의
            filename = f"webinar_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
            video_dir = "/tmp/videos" # Cloud Run은 /tmp 폴더에만 쓰기 권한이 있음
            if not os.path.exists(video_dir):
                os.makedirs(video_dir)

            try:
                with sync_playwright() as p:
                    # 사내 보안망 고려하여 브라우저 실행 옵션 최적화
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    context = browser.new_context(record_video_dir=video_dir)
                    page = context.new_page()
                    page.goto(url, wait_until="networkidle")
                    
                    # 지정된 시간 동안 녹화 대기
                    page.wait_for_timeout(duration * 60 * 1000)
                    browser.close()
                
                # 생성된 비디오 파일 찾기
                video_files = os.listdir(video_dir)
                if video_files:
                    local_video_path = os.path.join(video_dir, video_files[0])
                    
                    # Firebase Storage 업로드
                    blob = bucket.blob(f"recordings/{filename}")
                    blob.upload_from_filename(local_video_path)
                    print(f"✅ Firebase 업로드 완료: recordings/{filename}")
                    
                    # Supabase 완료 처리
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": blob.public_url
                    }).eq("id", job_id).execute()
                    
                    # 임시 파일 삭제
                    os.remove(local_video_path)
                else:
                    raise Exception("비디오 파일이 생성되지 않았습니다.")
                    
            except Exception as e:
                print(f"❌ 녹화 중 오류 발생: {e}")
                supabase.table("webinar_reservations").update({"status": "error"}).eq("id", job_id).execute()

    except Exception as e:
        print(f"❌ 데이터베이스 조회 중 오류 발생: {e}")

if __name__ == "__main__":
    run_recorder()