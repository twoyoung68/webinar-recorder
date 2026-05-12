# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.11 (Armor Edition)
# DESCRIPTION: 라이브러리 버전 충돌 완전 해결 및 유튜브 위장 강화
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

# [핵심] 라이브러리 로드 방식 변경 (에러 방지용)
try:
    from playwright.async_api import async_playwright
    import playwright_stealth
    import firebase_admin
    from firebase_admin import credentials, storage
    from supabase import create_client
except ImportError as e:
    logging.error(f"라이브러리 로드 실패: {e}")
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

async def apply_stealth(page):
    """라이브러리 버전에 상관없이 Stealth 모드를 적용하는 철벽 함수"""
    try:
        # 방식 1: stealth_async 시도
        if hasattr(playwright_stealth, 'stealth_async'):
            await playwright_stealth.stealth_async(page)
            logging.info("🛡️ Stealth_async 적용 완료")
        # 방식 2: 그냥 stealth 시도
        elif hasattr(playwright_stealth, 'stealth'):
            # sync 함수인 경우를 대비해 처리
            playwright_stealth.stealth(page)
            logging.info("🛡️ Stealth 적용 완료")
        else:
            logging.warning("⚠️ Stealth 함수를 찾을 수 없어 수동 위장을 실시합니다.")
            # 수동 위장: webdriver 속성 제거
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    except Exception as e:
        logging.warning(f"🛡️ Stealth 적용 중 오류 발생 (무시하고 진행): {e}")

async def human_emulation(page):
    """인간적인 움직임 시뮬레이션"""
    try:
        logging.info("🕵️ 인간 위장 동작 수행...")
        for _ in range(random.randint(3, 5)):
            x, y = random.randint(100, 800), random.randint(100, 500)
            await page.mouse.move(x, y, steps=25)
            await asyncio.sleep(random.uniform(0.5, 1.2))
    except: pass

async def click_play_button(page):
    """지능형 플레이 버튼 클릭"""
    try:
        await asyncio.sleep(random.uniform(8.0, 12.0))
        play_selectors = [
            "button[aria-label*='재생' i]", ".ytp-large-play-button", 
            "button[aria-label*='Play' i]", ".vjs-big-play-button"
        ]
        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                logging.info(f"🎯 버튼 발견: {selector}")
                await btn.click(delay=random.randint(300, 800))
                return True
        logging.info("⚠️ 버튼 탐색 실패, 중앙 클릭")
        await page.mouse.click(640, 360, delay=random.randint(300, 600))
    except: pass

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 v2.3.11 세션 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale="ko-KR", timezone_id="Asia/Seoul"
        )
        
        page = await context.new_page()
        
        # [철벽 보안 적용]
        await apply_stealth(page)
            
        try:
            await page.goto(job['webinar_url'], wait_until="networkidle", timeout=60000)
            await human_emulation(page)
            await click_play_button(page)

            # 녹화 진행
            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 5 == 0: logging.info(f"📹 촬영 중... {i+1}/{duration} 분")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info(f"✅ 업로드 완료: {remote_name}")
        except Exception as e:
            logging.error(f"❌ 에러 발생: {e}")
            await browser.close()

async def main():
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data: await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
