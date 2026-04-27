# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.3.0 (2026-04-28)
# DESCRIPTION: Stable Logic & Coordinate-based Clicking
# ==========================================

import os, json, pytz, pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright

BUCKET_NAME = "webinar-recordings-plant-ti" 
KST = pytz.timezone('Asia/Seoul')

if not _apps:
    info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"), strict=False)
    initialize_app(credentials.Certificate(info), {'storageBucket': f"{BUCKET_NAME}.appspot.com"})

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = storage.bucket(BUCKET_NAME)

def run_recorder():
    now_utc = datetime.now(pytz.utc)
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    
    for job in res.data:
        sched_utc = pd.to_datetime(job['scheduled_at']).astimezone(pytz.utc)
        
        if now_utc >= sched_utc:
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job['id']).execute()
            
            try:
                with sync_playwright() as p:
                    # 사람처럼 보이기 위한 브라우저 설정
                    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                    context = browser.new_context(
                        user_agent=user_agent,
                        viewport={'width': 854, 'height': 480}, 
                        record_video_dir="/tmp/videos/"
                    )
                    page = context.new_page()
                    
                    # 접속 및 넉넉한 대기
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=100000)
                    page.wait_for_timeout(10000) 

                    # [지능형 3회 클릭 시도]
                    for i in range(1, 4):
                        page.wait_for_timeout(5000)
                        try:
                            # (A) 중앙 좌표 클릭 (삼각형 재생 버튼 타격)
                            page.mouse.click(427, 240)
                            # (B) 텍스트 기반 버튼 탐색 클릭
                            for t in ["Play", "재생", "Join", "참가", "Confirm", "확인", "Enter", "입장"]:
                                btn = page.get_by_role("button", name=t, exact=False)
                                if btn.is_visible(): 
                                    btn.click()
                        except: pass

                    # 지정 시간만큼 녹화
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    path = page.video.path()
                    browser.close()
                    
                    # Firebase Storage 업로드
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(path)
                    
                    # 결과 URL 생성 (ACL 에러 방지 방식)
                    video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/recordings/{job['title']}_{job['id']}.webm"
                    
                    supabase.table("webinar_reservations").update({
                        "status": "completed", 
                        "video_url": video_url, 
                        "failure_reason": None
                    }).eq("id", job['id']).execute()

            except Exception as e:
                supabase.table("webinar_reservations").update({
                    "status": "error", 
                    "failure_reason": str(e)
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()