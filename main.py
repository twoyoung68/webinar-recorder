import os
import json
import pytz
import pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- 1. 기본 설정 및 연결 ---
BUCKET_NAME = "webinar-recordings-plant-ti" # 설정하신 버킷명 확인
KST = pytz.timezone('Asia/Seoul')

# Firebase 초기화
if not _apps:
    # GitHub Secrets에 저장된 서비스 계정 키 사용
    info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"), strict=False)
    initialize_app(credentials.Certificate(info), {
        'storageBucket': f"{BUCKET_NAME}.appspot.com"
    })

# Supabase 초기화
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = storage.bucket(BUCKET_NAME)

def run_recorder():
    # 1. 현재 절대 시각 (UTC 기준)
    now_utc = datetime.now(pytz.utc)
    print(f"[{datetime.now(KST)}] 스케줄러 작동 중... (현재 UTC: {now_utc})")

    # 2. 대기 중인 예약 작업 조회 (pending 또는 trigger 상태)
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    
    if not res.data:
        print("조회된 예약 작업이 없습니다.")
        return

    for job in res.data:
        # DB 저장 시각을 UTC로 변환하여 비교
        sched_utc = pd.to_datetime(job['scheduled_at']).astimezone(pytz.utc)
        
        # 예약 시간이 되었거나 지났다면 녹화 시작
        if now_utc >= sched_utc:
            print(f"🎬 녹화 시작 대상 발견: {job['title']}")
            
            # 상태 업데이트: running
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job['id']).execute()
            
            video_path = f"/tmp/{job['title']}_{job['id']}.webm"
            
            try:
                with sync_playwright() as p:
                    # 브라우저 실행 (Headless 모드)
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    # 녹화 설정 (480p 저용량 모드)
                    context = browser.new_context(
                        viewport={'width': 854, 'height': 480},
                        record_video_dir="/tmp/videos/",
                        record_video_size={'width': 854, 'height': 480}
                    )
                    page = context.new_page()
                    
                    # 웨비나 주소 접속
                    print(f"🔗 접속 중: {job['webinar_url']}")
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=90000)
                    page.wait_for_timeout(5000) # 로딩 안정화 대기

                    # [핵심 로직: 이메일 옆 확인 버튼 및 입장/플레이 클릭]
                    # 1. 이메일 입력창 주변 탐색
                    try:
                        # 이메일 주소가 이미 입력된 필드 찾기
                        email_field = page.query_selector("input[type='email'], input[name*='email'], input[value*='@']")
                        if email_field:
                            print(f"✅ 기입력된 이메일 발견: {email_field.input_value()}")
                            # 이메일 필드 주변의 버튼(확인, 입장 등)을 찾아 클릭 시도
                            confirm_btn = email_field.evaluate_handle("el => el.closest('div, form').querySelector('button, input[type=\"submit\"]')")
                            if confirm_btn:
                                confirm_btn.as_element().click()
                                print("✅ 이메일 옆 확인 버튼 클릭 완료")
                                page.wait_for_timeout(3000)
                    except Exception as e:
                        print(f"이메일 버튼 클릭 시도 중 건너뜀: {e}")

                    # 2. 일반적인 입장/플레이 버튼 전방위 탐색
                    entry_buttons = ["Confirm", "확인", "Join", "참가", "Enter", "입장", "Play", "재생", "OK"]
                    for b_text in entry_buttons:
                        try:
                            target = page.get_by_role("button", name=b_text, exact=False)
                            if target.is_visible():
                                target.click()
                                print(f"✅ 버튼 클릭 성공: {b_text}")
                                page.wait_for_timeout(2000)
                        except: continue

                    # 3. 중앙 플레이 아이콘 (SVG 등 모양 위주) 강제 클릭
                    try:
                        page.click("svg, .vjs-big-play-button, .play-icon", timeout=5000)
                        print("✅ 중앙 플레이 아이콘 클릭 시도 완료")
                    except: pass

                    # 지정된 시간만큼 녹화 유지
                    print(f"⏱️ 녹화 중... ({job['duration_min']}분 대기)")
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    
                    # 브라우저 종료 및 영상 경로 획득
                    path = page.video.path()
                    browser.close()
                    
                    # Firebase 업로드
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(path)
                    blob.make_public()
                    video_url = blob.public_url
                    
                    # 상태 업데이트: completed
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": video_url,
                        "is_downloaded": False
                    }).eq("id", job['id']).execute()
                    print(f"✅ 녹화 완료 및 업로드 성공: {job['title']}")

            except Exception as e:
                print(f"❌ 녹화 중 오류 발생: {e}")
                supabase.table("webinar_reservations").update({"status": "error"}).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()