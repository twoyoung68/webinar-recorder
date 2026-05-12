# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.9 (Evasion Edition)
# DESCRIPTION: 유튜브 봇 감지 회피 및 지능형 위장 로직
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
    logging.error(f"Missing Library: {e}")
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

async def human_emulation(page):
    """사람처럼 마우스를 움직이고 스크롤하는 위장 로직"""
    logging.info("🕵️ 위장 동작 시작 (Human Emulation)...")
    try:
        # 1. 랜덤 마우스 이동 (화면 곳곳을 훑음)
        for _ in range(random.randint(3, 6)):
            x, y = random.randint(100, 1000), random.randint(100, 600)
            await page.mouse.move(x, y, steps=random.randint(10, 20))
            await asyncio.sleep(random.uniform(0.2, 0.8))

        # 2. 미세한 스크롤 (읽는 척 하기)
        await page.mouse.wheel(0, random.randint(100, 300))
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.mouse.wheel(0, random.randint(-300, -100))
        
    except Exception as e:
        logging.info(f"위장 동작 중 경미한 오류: {e}")

async def click_play_button(page):
    """VOD 플레이 버튼을 찾아 지능적으로 클릭"""
    try:
        # 인간적인 대기
        await asyncio.sleep(random.uniform(6.0, 10.0))
        
        # 버튼 후보들
        play_selectors = [
            "button[aria-label*='재생' i]", 
            "button[aria-label*='Play' i]",
            ".ytp-large-play-button", # 유튜브 전용 버튼 클래스
            ".vjs-big-play-button",
            "xpath=//button[contains(@class, 'play')]"
        ]

        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                logging.info(f"🎯 플레이 버튼 발견: {selector}")
                # 마우스를 버튼 위로 천천히 이동 후 클릭
                box = await btn.bounding_box()
                if box:
                    await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=15)
                await btn.click(delay=random.randint(200, 600))
                return True
        
        # 못 찾으면 중앙 클릭
        logging.info("⚠️ 버튼 탐색 실패, 중앙 강제 클릭")
        await page.mouse.click(640, 360, delay=random.randint(200, 500))
        return True
    except Exception as e:
        logging.info(f"클릭 로직 건너뜀: {e}")

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 v2.3.9 위장 녹화 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        # [위장 1] 리얼 User-Agent 및 언어 설정
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            record_video_dir=str(video_dir),
            record_video_size={'width': 854, 'height': 480} # 약간 상향 (글자 선명도)
        )
        
        page = await context.new_page()
        # [위장 2] Stealth 라이브러리 강화 적용
        await playwright_stealth.stealth_async(page)
            
        try:
            # 주소 접속
            await page.goto(job['webinar_url'], wait_until="domcontentloaded", timeout=60000)
            
            # [위장 3] 사람처럼 행동하기
            await human_emulation(page)
            
            # 재생 버튼 클릭
            await click_play_button(page)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 위장 녹화 중... {i+1}/{duration} 분")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info("✅ 위장 업로드 성공")

        except Exception as e:
            logging.error(f"❌ 녹화 실패: {e}")
            await browser.close()

async def main():
    # (기존 main 로직과 동일)
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data: await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
