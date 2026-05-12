# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v2.3.7 (On-Demand Player Edition)
# DESCRIPTION: VOD 플레이 버튼 대응 녹화 엔진
# ==========================================

import os
import sys
import json
import asyncio
import logging
import random
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv

try:
    from playwright.async_api import async_playwright
    import playwright_stealth
    import firebase_admin
    from firebase_admin import credentials, storage
    from supabase import create_client
except ImportError as e:
    logging.error(f"Library missing: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# 서비스 초기화
try:
    firebase_admin.get_app()
except ValueError:
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    firebase_admin.initialize_app(credentials.Certificate(json.loads(cred_json, strict=False)), {
        'storageBucket': os.getenv('FIREBASE_BUCKET_NAME')
    })

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
bucket = storage.bucket()

async def click_play_button(page):
    """중앙의 플레이 버튼을 지능적으로 클릭 (VOD 대응)"""
    try:
        wait_time = random.uniform(5.0, 8.0)
        logging.info(f"⏳ 화면 로딩 대기... ({wait_time:.1f}초)")
        await asyncio.sleep(wait_time)

        play_selectors = [
            "button[aria-label*='Play' i]", "button:has-text('Play')",
            ".vjs-big-play-button", ".ytp-large-play-button"
        ]
        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                logging.info(f"🎯 플레이 버튼 클릭: {selector}")
                await btn.click(delay=random.randint(200, 500))
                return True
        
        logging.info("⚠️ 버튼 미발견, 화면 중앙 강제 클릭")
        await page.mouse.click(640, 360)
        return True
    except: return False

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 녹화 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=str(video_dir)
        )
        page = await context.new_page()
        
        # 스텔스 모드 적용
        if hasattr(playwright_stealth, 'stealth_async'):
            await playwright_stealth.stealth_async(page)
            
        try:
            await page.goto(job['webinar_url'], wait_until="networkidle", timeout=60000)
            await click_play_button(page)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 진행 중... {i+1}/{duration} 분")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info(f"✅ 완료: {remote_name}")
        except Exception as e:
            logging.error(f"❌ 실패: {e}")
            await browser.close()

async def main():
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data: await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
