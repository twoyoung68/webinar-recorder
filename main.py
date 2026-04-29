# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.6.0 (2026-04-29)
# DESCRIPTION: Universal Login Agent & Iframe Penetration
# ==========================================

import os, json, pytz, pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- 설정 ---
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
            shot1_url = ""
            
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width': 1280, 'height': 720}, record_video_dir="/tmp/videos/")
                    page = context.new_page()
                    
                    # 1. 접속 및 초기 대기
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=100000)
                    page.wait_for_timeout(10000) 

                    # [진단] 첫 번째 스크린샷 (로그인 전 상태 확인)
                    shot_path = f"/tmp/shot1_{job['id']}.png"
                    page.screenshot(path=shot_path)
                    bucket.blob(f"debug/shot1_{job['id']}.png").upload_from_filename(shot_path)
                    shot1_url = f"https://storage.googleapis.com/{BUCKET_NAME}/debug/shot1_{job['id']}.png"

                    # 2. [v1.6.0 지능형 로그인 시퀀스]
                    try:
                        # (A) "이미 등록됨/로그인" 버튼 찾기
                        login_gate = page.get_by_text("Already registered", exact=False).or_(
                            page.get_by_role("button", name="Login", exact=False)
                        ).or_(
                            page.get_by_text("Sign in", exact=False)
                        )
                        
                        if login_gate.first.is_visible():
                            login_gate.first.click()
                            page.wait_for_timeout(3000)
                        
                        # (B) 이메일 입력 (DB에 저장된 email 활용)
                        email_field = page.get_by_placeholder("email", exact=False).or_(
                            page.locator("input[type='email']")
                        ).or_(
                            page.locator("input[name*='email']")
                        )
                        
                        if email_field.first.is_visible():
                            email_field.first.fill(job['email'])
                            page.wait_for_timeout(1000)
                            
                            # (C) 최종 제출 버튼 클릭
                            submit_btn = page.get_by_role("button", name="Login", exact=True).or_(
                                page.get_by_role("button", name="Submit", exact=False)
                            ).or_(
                                page.locator("button[type='submit']")
                            )
                            submit_btn.first.click()
                            page.wait_for_timeout(5000) # 로그인 처리 대기
                    except Exception as e:
                        print(f"로그인 시도 중 건너뜀: {e}")

                    # 3. [기존 로직] 중앙 재생 버튼 및 아이프레임 탐색
                    page.mouse.click(640, 360) 
                    for frame in page.frames:
                        try:
                            play_btn = frame.get_by_role("button", name="Play", exact=False).or_(
                                frame.get_by_label("Play", exact=False)
                            )
                            if play_btn.is_visible(): play_btn.click()
                        except: pass

                    # 4. 녹화 진행
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    video_path = page.video.path()
                    browser.close()
                    
                    # 5. 업로드 및 결과 보고
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(video_path)
                    video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/recordings/{job['title']}_{job['id']}.webm"
                    
                    supabase.table("webinar_reservations").update({
                        "status": "completed", 
                        "video_url": video_url, 
                        "failure_reason": f"정상완료 / 진단샷: {shot1_url}"
                    }).eq("id", job['id']).execute()

            except Exception as e:
                supabase.table("webinar_reservations").update({
                    "status": "error", 
                    "failure_reason": f"에러: {str(e)} / 진단샷: {shot1_url}"
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()