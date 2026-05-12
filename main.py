# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v2.3.7 (Engine Base)
# DESCRIPTION: 캘린더 신호 기반 자동 녹화 엔진
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
except ImportError:
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# 초기화
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
    """v2.3.7 표준 플레이 버튼 클릭 로직"""
    try:
        await asyncio.sleep(8.0)
        play_selectors = ["button[aria-label*='Play' i]", ".vjs-big-play-button", ".ytp-large-play-button"]
        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                await btn.click(delay=random.randint(200, 500))
                return True
        await page.mouse.click(640, 360)
        return True
    except: return False

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 녹화 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1280, 'height': 720}, record_video_dir=str(video_dir))
        page = await context.new_page()
        
        try:
            await page.goto(job['webinar_url'], wait_until="networkidle", timeout=60000)
            await click_play_button(page)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 촬영 중... {i+1}/{duration} 분")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info(f"✅ 완료")
        except Exception as e:
            logging.error(f"❌ 실패: {e}")
            await browser.close()

async def main():
    # 캘린더 신호(CALENDAR_URL)가 환경 변수로 들어왔는지 확인
    cal_url = os.getenv("CALENDAR_URL")
    cal_title = os.getenv("CALENDAR_TITLE") or "Calendar Event"

    if cal_url:
        # 캘린더 정보를 DB에 먼저 기록 (이후 스트림릿 현황에 나타남)
        res = supabase.table("webinar_reservations").insert({
            "title": cal_title, "webinar_url": cal_url, "status": "running", "duration_min": 60,
            "scheduled_at": dt.datetime.now(dt.timezone.utc).isoformat()
        }).execute()
        if res.data:
            await record_webinar(res.data[0])
    else:
        # 기존 DB 예약건 확인 (10분 간격 체크용)
        res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
        for job in res.data: await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
