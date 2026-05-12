# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v2.3.7 (On-Demand Player Edition)
# DESCRIPTION: VOD 플레이 버튼 탐지 및 지능형 클릭 로직 추가
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

try:
    from playwright.async_api import async_playwright
    import playwright_stealth
    import firebase_admin
    from firebase_admin import credentials, storage
    from supabase import create_client
except ImportError as e:
    print(f"Library missing: {e}")
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
    """중앙의 빨간 플레이 버튼 등을 인간처럼 클릭"""
    try:
        # 1. 인간처럼 5~8초 정도 기다림 (화면 로딩 및 자연스러운 동작)
        wait_time = random.uniform(5.0, 8.0)
        logging.info(f"⏳ 화면 로딩 대기 중... ({wait_time:.1f}초)")
        await asyncio.sleep(wait_time)

        # 2. 플레이 버튼 찾기 (우선순위별 탐색)
        # - Play라는 텍스트나 라벨이 있는 버튼
        # - 중앙에 위치한 큰 삼각형 아이콘/버튼
        play_selectors = [
            "button[aria-label*='Play' i]", 
            "button:has-text('Play')",
            ".play-button",
            ".vjs-big-play-button", # 일반적인 비디오 플레이어 클래스
            "svg[viewBox*='0 0 16 16']", # 재생 아이콘 모양
            "xpath=//button[contains(@class, 'play')]"
        ]

        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                logging.info(f"🎯 플레이 버튼 발견 ({selector}), 클릭 시도...")
                # 버튼 중앙으로 마우스 이동 후 클릭 (인간적인 동작)
                await btn.scroll_into_view_if_needed()
                await btn.click(delay=random.randint(100, 500)) 
                logging.info("✅ 재생 시작!")
                return True
        
        # 3. 만약 버튼을 못 찾았다면 화면 중앙 강제 클릭 (최후의 수단)
        logging.info("⚠️ 특정 버튼을 못 찾아 화면 중앙을 클릭합니다.")
        await page.mouse.click(640, 360) 
        return True

    except Exception as e:
        logging.info(f"ℹ️ 플레이 버튼 클릭 시퀀스 건너뜀: {e}")
        return False

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 녹화 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
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
            
            # [신규 로직] 플레이 버튼 클릭 시퀀스 실행
            await click_play_button(page)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 녹화 중... {i+1}/{duration} 분")

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
                logging.info(f"✅ 파이어베이스 업로드 완료: {remote_name}")

        except Exception as e:
            logging.error(f"❌ 녹화 실패: {e}")
            await browser.close()

async def main():
    cal_title = os.getenv("CALENDAR_TITLE")
    cal_url = os.getenv("CALENDAR_URL")

    if cal_title and cal_url:
        job = {"id": f"cal_{dt.datetime.now().strftime('%H%M%S')}", "title": cal_title, "webinar_url": cal_url, "duration_min": 60}
        await record_webinar(job)
        return

    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data:
        await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
