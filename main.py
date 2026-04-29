# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.5.2 (2026-04-29)
# DESCRIPTION: Iframe Penetration & Double Debug Screenshots
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
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width': 1280, 'height': 720}, record_video_dir="/tmp/videos/")
                    page = context.new_page()
                    
                    # 1. 접속 및 초기 대기
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=100000)
                    page.wait_for_timeout(10000) 

                    # [v1.5.2] 진단용 스크린샷 1 (접속 직후)
                    shot1_path = f"/tmp/shot1_{job['id']}.png"
                    page.screenshot(path=shot1_path)
                    bucket.blob(f"debug/shot1_{job['id']}.png").upload_from_filename(shot1_path)
                    shot1_url = f"https://storage.googleapis.com/{BUCKET_NAME}/debug/shot1_{job['id']}.png"

                    # 2. [강화] 아이프레임 내부 버튼 탐색 및 클릭
                    click_log = []
                    try:
                        # (A) 메인 페이지 중앙 클릭
                        page.mouse.click(640, 360)
                        
                        # (B) 모든 액자(Iframe) 내부 탐색
                        for frame in page.frames:
                            for t in ["Play", "재생", "Join", "참가"]:
                                btn = frame.get_by_role("button", name=t, exact=False)
                                if btn.is_visible():
                                    btn.click()
                                    click_log.append(f"Frame버튼:{t}")
                    except Exception as e:
                        click_log.append(f"클릭오류:{str(e)[:20]}")

                    # 3. 녹화 진행
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    video_path = page.video.path()
                    browser.close()
                    
                    # 4. 결과 업로드
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(video_path)
                    video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/recordings/{job['title']}_{job['id']}.webm"
                    
                    # 5. DB 업데이트
                    supabase.table("webinar_reservations").update({
                        "status": "completed", 
                        "video_url": video_url, 
                        "failure_reason": f"클릭:{','.join(click_log)} / 진단샷: {shot1_url}"
                    }).eq("id", job['id']).execute()

            except Exception as e:
                supabase.table("webinar_reservations").update({
                    "status": "error", 
                    "failure_reason": f"에러: {str(e)} / 진단샷: {shot1_url if 'shot1_url' in locals() else '없음'}"
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()