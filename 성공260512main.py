
# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v2.3.5 (Integrated & Optimized)
# ==========================================

import os
import sys
import json
import asyncio
import logging
import re
import random
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv
from datetime import timezone

# 라이브러리 로드
try:
    from playwright.async_api import async_playwright
    import playwright_stealth
    import firebase_admin
    from firebase_admin import credentials, storage
    from supabase import create_client
except ImportError as e:
    print(f"Required library missing: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# 서비스 초기화
try:
    firebase_admin.get_app()
except ValueError:
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_info = json.loads(cred_json, strict=False)
    firebase_admin.initialize_app(credentials.Certificate(cred_info), {
        'storageBucket': os.getenv('FIREBASE_BUCKET_NAME')
    })

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
bucket = storage.bucket()

async def handle_login(page, user_email):
    """지능형 로그인 시퀀스 (Gasworld 등 대응)"""
    try:
        reg_link = page.get_by_role("link", name=re.compile(r"CLICK HERE TO LOGIN|ALREADY REGISTERED", re.IGNORECASE))
        if await reg_link.is_visible(timeout=5000):
            await reg_link.click()
            await asyncio.sleep(3)

        email_input = page.locator("input[type='email'], input[placeholder*='email' i]").first
        if await email_input.is_visible(timeout=5000):
            await email_input.fill(user_email)
            await asyncio.sleep(1)
            submit_btn = page.get_by_text(re.compile(r"(login|join|submit|enter|watch)", re.IGNORECASE)).first
            await submit_btn.click()
            logging.info("✅ Login sequence completed.")
    except Exception as e:
        logging.info(f"ℹ️ Login skipped or handled: {e}")

async def record_webinar(job):
    """핵심 녹화 및 업로드 엔진"""
    async with async_playwright() as p:
        logging.info(f"🎬 Starting record: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        
        # [화질 절반 최적화 적용]
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=str(video_dir),
            record_video_size={'width': 640, 'height': 360} 
        )
        
        page = await context.new_page()
        if hasattr(playwright_stealth, 'stealth_async'):
            await playwright_stealth.stealth_async(page)
            
        try:
            await page.goto(job['webinar_url'], wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)
            
            user_email = os.getenv("USER_EMAIL", "plant_ti_bot@daewoo.com")
            await handle_login(page, user_email)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 Recording... {i+1}/{duration} min")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({
                    "status": "completed", "video_url": remote_name
                }).eq("id", job['id']).execute()
                logging.info(f"✅ Upload success: {remote_name}")

        except Exception as e:
            logging.error(f"❌ Error during recording: {e}")
            await browser.close()

async def main():
    # 1. Google Calendar 데이터 우선 처리
    cal_title = os.getenv("CALENDAR_TITLE")
    cal_url = os.getenv("CALENDAR_URL")

    if cal_title and cal_url:
        job = {
            "id": f"cal_{dt.datetime.now().strftime('%H%M%S')}",
            "title": cal_title,
            "webinar_url": cal_url,
            "duration_min": 60
        }
        await record_webinar(job)
        return

    # 2. Supabase 예약 확인 (백업)
    now_utc = dt.datetime.now(timezone.utc)
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data:
        await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
