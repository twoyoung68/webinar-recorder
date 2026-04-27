import os
import json
import pytz
import pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- 1. 환경 설정 ---
BUCKET_NAME = "webinar-recordings-plant-ti" # 설정된 Firebase 버킷명
KST = pytz.timezone('Asia/Seoul')

# Firebase & Supabase 초기화
if not _apps:
    info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"), strict=False)
    initialize_app(credentials.Certificate(info), {'storageBucket': f"{BUCKET_NAME}.appspot.com"})

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = storage.bucket(BUCKET_NAME)

def run_recorder():
    now_utc = datetime.now(pytz.utc)
    print(f"[{datetime.now(KST)}] 스케줄러 가동 중 (UTC: {now_utc})")

    # 대기 중인 작업 조회
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    
    if not res.data:
        return

    for job in res.data:
        sched_utc = pd.to_datetime(job['scheduled_at']).astimezone(pytz.utc)
        
        if now_utc >= sched_utc:
            print(f"🎬 녹화 시작: {job['title']}")
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job['id']).execute()
            
            try:
                with sync_playwright() as p:
                    # 브라우저 환경 설정
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    context = browser.new_context(
                        viewport={'width': 854, 'height': 480},
                        record_video_dir="/tmp/videos/",
                        record_video_size={'width': 854, 'height': 480}
                    )
                    page = context.new_page()
                    
                    # 1. 사이트 접속
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=90000)
                    
                    # 2. [지능형 3단계 클릭 로직] 사용자 지침 반영
                    targets = ["Play", "재생", "Join", "참가", "Confirm", "확인", "Enter", "입장", "OK"]
                    
                    for i in range(1, 4):
                        print(f"🖱️ {i}차 클릭 시도 중 (5초 간격)...")
                        page.wait_for_timeout(5000)
                        
                        # (A) 이메일 확인 버튼 클릭 (기입력된 이메일 옆 버튼 타격)
                        try:
                            email_input = page.query_selector("input[type='email'], input[value*='@']")
                            if email_input:
                                btn = email_input.evaluate_handle("el => el.closest('div, form').querySelector('button, input[type=\"submit\"]')")
                                if btn: 
                                    btn.as_element().click()
                                    print("✅ 이메일 인접 확인 버튼 클릭 성공")
                        except: pass

                        # (B) 텍스트 기반 버튼 클릭
                        for t in targets:
                            try:
                                btn = page.get_by_role("button", name=t, exact=False)
                                if btn.is_visible(): 
                                    btn.click()
                                    print(f"✅ 버튼 클릭 성공: {t}")
                            except: continue

                        # (C) 플레이 아이콘(SVG) 강제 클릭
                        try:
                            page.click("svg, .vjs-big-play-button, .play-icon", timeout=3000)
                            print("✅ 플레이 아이콘 클릭 시도 완료")
                        except: pass

                    # 3. 실제 녹화 진행
                    print(f"⏱️ 녹화 중... ({job['duration_min']}분)")
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    
                    # 4. 영상 파일 처리 및 업로드
                    video_path = page.video.path()
                    browser.close()
                    
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(video_path)
                    blob.make_public()
                    
                    # 성공 시 업데이트
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": blob.public_url,
                        "is_downloaded": False,
                        "failure_reason": None
                    }).eq("id", job['id']).execute()
                    print(f"✅ {job['title']} 녹화 완료")

            except Exception as e:
                # [중요] 실패 원인 기록 로직
                error_msg = str(e)
                print(f"❌ 녹화 실패: {error_msg}")
                supabase.table("webinar_reservations").update({
                    "status": "error",
                    "failure_reason": error_msg
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()