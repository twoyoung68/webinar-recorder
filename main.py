import os
import firebase_admin
from firebase_admin import credentials, storage
from supabase import create_client
import json
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright

# --- [수정] 새 버킷 이름 설정 ---
NEW_BUCKET_NAME = "webinar-recordings-plant-ti" 

# [1. Firebase 인증 로직]
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_json:
        try:
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
            print("✅ Firebase: 환경 변수 인증 성공")
        except Exception as e:
            print(f"❌ Firebase: 인증 실패: {e}")
            cred = None
    else:
        json_path = os.path.join(os.path.dirname(__file__), 'firebase_key.json')
        if os.path.exists(json_path):
            cred = credentials.Certificate(json_path)
            print("✅ Firebase: 로컬 파일 인증 성공")
        else:
            print("⚠️ Firebase: 인증 정보를 찾을 수 없습니다.")
            cred = None
    
    if cred:
        # [수정] 초기화 시 새 버킷 이름을 정확히 명시합니다.
        firebase_admin.initialize_app(cred, {
            'storageBucket': f"{NEW_BUCKET_NAME}.appspot.com"
        })

# [2. Supabase 설정]
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Firebase Storage 버킷 참조 (명시적 지정)
bucket = storage.bucket(NEW_BUCKET_NAME)

def run_recorder():
    if supabase is None:
        print("🛑 Supabase 설정 미비로 중단합니다.")
        return

    print("🔎 녹화 대상 확인 중...")
    now_utc = datetime.now(pytz.utc).isoformat()
    
    try:
        # pending 또는 trigger 상태인 작업을 가져옴
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
            # [추가] 사용자가 입력한 웨비나 명칭 가져오기
            webinar_title = job.get('title', 'Untitled').replace(" ", "_")
            
            print(f"🎬 녹화 시작: [{webinar_title}] {url} ({duration}분)")
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job_id).execute()
            
            # [수정] 파일명에 웨비나 제목을 포함하여 찾기 쉽게 변경
            filename = f"{webinar_title}_{datetime.now().strftime('%m%d_%H%M')}.webm"
            video_dir = "/tmp/videos"
            if not os.path.exists(video_dir): os.makedirs(video_dir)

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    
                    # [화질 수정] 720p의 절반 수준인 480p(854x480)로 설정하여 용량 최적화
                    context = browser.new_context(
                        viewport={'width': 854, 'height': 480},
                        record_video_dir=video_dir,
                        record_video_size={'width': 854, 'height': 480}
                    )
                    
                    page = context.new_page()
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    
                    # 녹화 지속 (분 단위 -> 밀리초)
                    page.wait_for_timeout(duration * 60 * 1000)
                    browser.close()
                
                # 생성된 파일 처리
                video_files = [f for f in os.listdir(video_dir) if f.endswith('.webm')]
                if video_files:
                    local_video_path = os.path.join(video_dir, video_files[0])
                    
                    # [수정] 새 버킷의 recordings 폴더로 업로드
                    blob = bucket.blob(f"recordings/{filename}")
                    blob.upload_from_filename(local_video_path)
                    
                    print(f"✅ 업로드 완료: {NEW_BUCKET_NAME}/recordings/{filename}")
                    
                    # 완료 처리
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": f"https://storage.googleapis.com/{NEW_BUCKET_NAME}/recordings/{filename}"
                    }).eq("id", job_id).execute()
                    
                    os.remove(local_video_path)
                else:
                    raise Exception("비디오 파일 생성 실패")
                    
            except Exception as e:
                print(f"❌ 녹화 에러: {e}")
                supabase.table("webinar_reservations").update({"status": "error"}).eq("id", job_id).execute()

    except Exception as e:
        print(f"❌ DB 조회 에러: {e}")

if __name__ == "__main__":
    run_recorder()