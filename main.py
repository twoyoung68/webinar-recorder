# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.4.2 (Cookie Vault Edition)
# DESCRIPTION: 도메인별 쿠키 자동 주입 및 듀얼 하이브리드 녹화 엔진
# ==========================================

import os
import sys
import json
import asyncio
import logging
import random
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# 필수 라이브러리 로드
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

# --- 1. 서비스 초기화 ---
try:
    firebase_admin.get_app()
except ValueError:
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    firebase_admin.initialize_app(credentials.Certificate(json.loads(cred_json, strict=False)), {
        'storageBucket': os.getenv('FIREBASE_BUCKET_NAME')
    })

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
bucket = storage.bucket()

# --- 2. 위장 및 자동화 함수군 ---

async def apply_stealth(page):
    """버전 호환성을 고려한 Stealth 위장 적용"""
    try:
        if hasattr(playwright_stealth, 'stealth_async'):
            await playwright_stealth.stealth_async(page)
        elif hasattr(playwright_stealth, 'stealth'):
            playwright_stealth.stealth(page)
        logging.info("🛡️ Stealth 위장 모드 활성화")
    except Exception as e:
        logging.warning(f"🛡️ Stealth 적용 건너뜀: {e}")

async def human_emulation(page):
    """인간적인 마우스 움직임 시뮬레이션"""
    try:
        for _ in range(random.randint(3, 5)):
            x, y = random.randint(200, 1000), random.randint(150, 600)
            await page.mouse.move(x, y, steps=25)
            await asyncio.sleep(random.uniform(0.5, 1.2))
    except: pass

async def click_play_button(page):
    """플레이 버튼 탐지 및 클릭"""
    try:
        await asyncio.sleep(random.uniform(7.0, 12.0))
        play_selectors = [
            "button[aria-label*='재생' i]", ".ytp-large-play-button", 
            "button[aria-label*='Play' i]", ".vjs-big-play-button",
            "button.play", "svg[viewBox*='0 0 16 16']"
        ]
        for selector in play_selectors:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=3000):
                logging.info(f"🎯 버튼 발견 및 클릭: {selector}")
                await btn.click(delay=random.randint(300, 800))
                return True
        logging.info("⚠️ 버튼 미발견, 화면 중앙 클릭 수행")
        await page.mouse.click(640, 360, delay=random.randint(300, 600))
    except: pass

# --- 3. 핵심 녹화 엔진 ---

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 v2.4.2 녹화 시작: {job.get('title')}")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        # [STEP 1] 도메인 분석 및 쿠키 금고 조회
        parsed_url = urlparse(job['webinar_url'])
        domain = parsed_url.netloc.replace("www.", "").lower()
        
        # [STEP 2] 브라우저 실행 모드 결정
        try:
            # 근무 중: 로컬 크롬 연결 시도 (포트 9222)
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            logging.info(f"🖥️ 로컬 하이브리드 모드 연결 성공 (Domain: {domain})")
        except:
            # 야간/부재 시: 클라우드 스텔스 모드
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720},
                locale="ko-KR", timezone_id="Asia/Seoul",
                record_video_dir=str(video_dir),
                record_video_size={'width': 1280, 'height': 720}
            )
            
            # [Cookie Vault] 금고에서 해당 도메인의 쿠키가 있는지 확인
            res_cookie = supabase.table("webinar_cookies").select("cookie_data").eq("domain", domain).execute()
            if res_cookie.data:
                await context.add_cookies(res_cookie.data[0]['cookie_data'])
                logging.info(f"🍪 금고에서 {domain} 전용 쿠키를 꺼내 주입했습니다.")
            
            logging.info("☁️ 클라우드 스텔스 모드 활성화")

        page = await context.new_page()
        await apply_stealth(page)
            
        try:
            # 주소 접속
            await page.goto(job['webinar_url'], wait_until="domcontentloaded", timeout=90000)
            
            # 위장 동작 및 재생 시작
            await human_emulation(page)
            await click_play_button(page)

            # 녹화 대기 루프
            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                if i % 10 == 0: logging.info(f"📹 촬영 중... {i+1}/{duration} 분")

            # 종료 및 업로드
            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                file_id = job['id']
                timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                remote_name = f"webinars/{file_id}_{timestamp}.webm"
                
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                
                # DB 상태 업데이트
                supabase.table("webinar_reservations").update({
                    "status": "completed", 
                    "video_url": remote_name
                }).eq("id", job['id']).execute()
                logging.info(f"✅ 파일 업로드 완료: {remote_name}")

        except Exception as e:
            logging.error(f"❌ 녹화 세션 에러: {e}")
            await browser.close()

async def main():
    # 처리 대기 중인 예약건 확인
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    if not res.data:
        logging.info("💤 처리할 예약 일정이 없습니다.")
        return
        
    for job in res.data:
        await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
