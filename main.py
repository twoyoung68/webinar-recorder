# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.10 (Ultimate Evasion)
# DESCRIPTION: Stealth 라이브러리 에러 수정 및 위장 로직 강화
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

# 필수 라이브러리 로드
try:
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async  # 호출 방식 변경
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

async def human_emulation(page):
    """인간처럼 마우스와 스크롤을 조작하여 유튜브 감지 우회"""
    logging.info("🕵️ 인간 위장 동작 수행 중...")
    try:
        # 1. 자연스러운 마우스 이동 (지그재그)
        for _ in range(random.randint(4, 7)):
            x, y = random.randint(200, 900), random.randint(150, 500)
            await page.mouse.move(x, y, steps=random.randint(15, 30))
            await asyncio.sleep(random.uniform(0.3, 1.0))

        # 2. 페이지 스크롤 (관심 있는 척)
        await page.mouse.wheel(0, random.randint(150, 400))
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await page.mouse.wheel(0, random.randint(-400, -150))
    except Exception as e:
        logging.info(f"위장 동작 중 무시 가능한 에러: {e}")

async def click_play_button(page):
    """지능형 플레이 버튼 클릭 로직"""
    try:
        # 화면이 안정될 때까지 충분히 대기
        await asyncio.sleep(random.uniform(7.0, 11.0))
        
        play_selectors = [
            "button[aria-label*='재생' i]", 
            "button[aria-label*='Play' i]",
            ".ytp-large-play-button", 
            ".vjs-big-play-button",
            "xpath=//button[contains(@class, 'play')]"
        ]

        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=4000):
                logging.info(f"🎯 플레이 버튼 조준 완료: {selector}")
                # 마우스 타겟팅 시각화
                box = await btn.bounding_box()
                if box:
                    await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=20)
                await btn.click(delay=random.randint(300, 700))
                logging.info("▶️ 재생 시작!")
                return True
        
        logging.info("⚠️ 버튼 탐색 실패, 정중앙 강제 클릭 수행")
        await page.mouse.click(640, 360, delay=random.randint(300, 600))
        return True
    except Exception as e:
        logging.info(f"클릭 시퀀스 예외 발생: {e}")

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 v2.3.10 녹화 세션 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        # 브라우저 컨텍스트 설정 (최대한 일반 사용자처럼)
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            record_video_dir=str(video_dir),
            record_video_size={'width': 1280, 'height': 720} # 유튜브 선명도를 위해 해상도 복구
        )
        
        page = await context.new_page()
        
        # [수정 포인트] Stealth 적용 방식 변경 및 예외 처리
        try:
            await stealth_async(page)
            logging.info("🛡️ Stealth 위장 모드 활성화 완료")
        except Exception as e:
            logging.warning(f"🛡️ Stealth 적용 실패 (무시하고 진행): {e}")
            
        try:
            # 주소 이동
            await page.goto(job['webinar_url'], wait_until="domcontentloaded", timeout=60000)
            
            # 사람 흉내내기 시동
            await human_emulation(page)
            
            # 플레이 버튼 클릭
            await click_play_button(page)

            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 촬영 진행 중... {i+1}/{duration} 분")

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
            logging.error(f"❌ 세션 종료 에러: {e}")
            await browser.close()

async def main():
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data: await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
