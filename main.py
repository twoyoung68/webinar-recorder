import os
import firebase_admin
from firebase_admin import credentials, storage
from supabase import create_client
import json
from datetime import datetime
import pytz
import pandas as pd
from playwright.sync_api import sync_playwright

# --- [설정] 글로벌 환경 변수 및 버킷 이름 ---
NEW_BUCKET_NAME = "webinar-recordings-plant-ti"
KST = pytz.timezone('Asia/Seoul')

# [1. Firebase/GCS 인증 로직]
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_json:
        try:
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
            print("✅ Firebase: 환경 변수 인증 성공")
        except Exception as e:
            print(f"❌ Firebase: JSON 파싱 실패 (키 확인 필요): {e}")
            cred = None
    else:
        # 로컬 테스트용 (파일이 있을 경우)
        json_path = os.path.join(os.path.dirname(__file__), 'firebase_key.json')
        cred = credentials.Certificate(json_path) if os.path.exists(json_path) else None
    
    if cred:
        firebase_admin.initialize_app(cred, {
            'storageBucket': f"{NEW_BUCKET_NAME}.appspot.com"
        })

# [2. Supabase 설정]
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# GCS 버킷 참조
bucket = storage.bucket(NEW_BUCKET_NAME)

def run_recorder():
    if supabase is None:
        print("🛑 Supabase 설정이 누락되어 실행을 중단합니다.")
        return

    print("🔎 녹화 대상 확인 중...")
    now_utc = datetime.now(pytz.utc).isoformat()
    
    try:
        # 현재 시간 이전에 시작해야 하는 pending/trigger 상태의 작업을 가져옴
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
            webinar_title = job.get('title', 'Untitled').replace(" ", "_")
            
            # 저장된 타임존 이름으로 현지 시각 계산 (로그 출력용)
            saved_tz_name = job.get('timezone_name', '대한민국 (KST)')
            # WORLD_ZONES 딕셔너리가 main.py에도 정의되어 있어야 함 (아래 함수 외부에 정의 권장)
            # 여기서는 편의상 Asia/Seoul을 기본값으로 사용
            
            print(f"🎬 녹화 시작: [{webinar_title}] {url} ({duration}분)")
            
            # 상태 업데이트: running
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job_id).execute()
            
            # 파일명 설정 (특수문자 제거)
            clean_title = "".join(c for c in webinar_title if c.isalnum() or c in (' ', '_')).rstrip()
            filename = f"{clean_title}_{datetime.now(KST).strftime('%m%d_%H%M')}.webm"
            video_dir = "/tmp/videos"
            if not os.path.exists(video_dir): os.makedirs(video_dir)

            try:
                with sync_playwright() as p:
                    # 브라우저 실행
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    
                    # [핵심] 화질 최적화: 480p (854x480) 설정
                    context = browser.new_context(
                        viewport={'width': 854, 'height': 480},
                        record_video_dir=video_dir,
                        record_video_size={'width': 854, 'height': 480}
                    )
                    
                    page = context.new_page()
                    print(f"🌐 페이지 접속 중... ({url})")
                    page.goto(url, wait_until="networkidle", timeout=90000)
                    
                    # --- [지능형 자동 클릭 로직] ---
                    print("🤖 자동 입장 버튼 탐색 중...")
                    click_targets = [
                        "Join", "참가", "Enter", "입장", "Accept", "수락", 
                        "OK", "확인", "Got it", "Allow", "Yes", "I agree",
                        "Launch", "시작", "Meeting", "참여"
                    ]
                    
                    # 15초 동안 3초 간격으로 버튼을 찾아 클릭 시도
                    for _ in range(5):
                        for target in click_targets:
                            try:
                                # 대소문자 구분 없이 텍스트가 포함된 버튼 찾기
                                button = page.get_by_role("button", name=target, exact=False)
                                if button.is_visible():
                                    button.click()
                                    print(f"✅ '{target}' 버튼을 자동으로 클릭했습니다.")
                                    page.wait_for_timeout(2000)
                            except:
                                continue
                        page.wait_for_timeout(3000)
                    # --- 자동 클릭 끝 ---

                    print(f"⏺️ 녹화 진행 중... ({duration}분 대기)")
                    page.wait_for_timeout(duration * 60 * 1000)
                    browser.close()
                
                # 생성된 비디오 파일 업로드
                video_files = [f for f in os.listdir(video_dir) if f.endswith('.webm')]
                if video_files:
                    # 가장 최근에 생성된 파일 선택
                    local_video_path = os.path.join(video_dir, video_files[0])
                    
                    # GCS 업로드
                    blob = bucket.blob(f"recordings/{filename}")
                    blob.upload_from_filename(local_video_path)
                    
                    # 공개 URL 생성 (버킷 권한이 '공개'로 되어 있어야 함)
                    video_public_url = f"https://storage.googleapis.com/{NEW_BUCKET_NAME}/recordings/{filename}"
                    
                    print(f"✅ 업로드 완료: {video_public_url}")
                    
                    # Supabase 상태 업데이트: completed
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": video_public_url
                    }).eq("id", job_id).execute()
                    
                    # 임시 파일 삭제
                    os.remove(local_video_path)
                else:
                    raise Exception("비디오 파일이 생성되지 않았습니다.")
                    
            except Exception as e:
                print(f"❌ 녹화 과정 오류: {e}")
                supabase.table("webinar_reservations").update({"status": "error"}).eq("id", job_id).execute()

    except Exception as e:
        print(f"❌ 데이터베이스 조회 오류: {e}")

if __name__ == "__main__":
    run_recorder()