# main.py
import os
import sys
import json
import asyncio
import logging
import re
import random
import pandas as pd
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv
from datetime import timezone

# --- [1. 초기화] ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

try:
    from playwright.async_api import async_playwright
    import playwright_stealth
    import firebase_admin
    from firebase_admin import credentials, storage
    from supabase import create_client
except ImportError as e:
    logging.critical(f"❌ 필수 라이브러리 누락: {e}")
    sys.exit(1)

# Firebase/Supabase 설정
try:
    firebase_admin.get_app()
except ValueError:
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_info = json.loads(cred_json, strict=False)
    firebase_admin.initialize_app(credentials.Certificate(cred_info), {'storageBucket': os.getenv('FIREBASE_BUCKET_NAME')})

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
bucket = storage.bucket()

# --- [2. 인간미 로직] ---
async def apply_stealth(page):
    try:
        if hasattr(playwright_stealth, 'stealth_async'): await getattr(playwright_stealth, 'stealth_async')(page)
        elif hasattr(playwright_stealth, 'stealth'): await getattr(playwright_stealth, 'stealth')(page)
    except: pass

async def human_move_and_click(page, element):
    box = await element.bounding_box()
    if not box: return
    tx, ty = box['x'] + box['width']/2, box['y'] + box['height']/2
    await page.mouse.move(tx - random.randint(50, 150), ty + random.randint(30, 70), steps=10)
    await asyncio.sleep(random.uniform(0.3, 0.6))
    await page.mouse.move(tx, ty, steps=15)
    await page.mouse.click(tx, ty, delay=random.randint(100, 250))

async def human_type(page, selector, text):
    await page.click(selector)
    for char in text:
        await page.type(selector, char, delay=random.randint(60, 150))

# --- [3. 지능형 로그인 (Gasworld 및 일반 대응)] ---
async def handle_login(page, user_email):
    h = page.viewport_size['height']
    # 1. 기등록자 클릭 (Gasworld 스타일)
    reg_link = page.get_by_role("link", name=re.compile(r"CLICK HERE TO LOGIN|ALREADY REGISTERED", re.IGNORECASE))
    if await reg_link.is_visible(timeout=5000):
        await human_move_and_click(page, reg_link)
        await asyncio.sleep(4)

    # 2. 이메일 입력 및 로그인 (중앙 영역 우선)
    email_selector = "input[type='email'], input[placeholder*='email' i]"
    email_input = page.locator(email_selector).first
    if await email_input.is_visible(timeout=5000):
        input_box = await email_input.bounding_box()
        if input_box and (h * 0.15 < input_box['y'] < h * 0.85):
            await human_type(page, email_selector, user_email)
            # 주변 Login/Join 버튼 클릭
            submit_btn = page.get_by_text(re.compile(r"(login|join|submit|enter|watch)", re.IGNORECASE)).first
            await human_move_and_click(page, submit_btn)
            await asyncio.sleep(5)
    else:
        logging.info("✅ 일반 화면 혹은 이미 입장된 상태로 판단됩니다.")

# --- [4. 녹화 엔진] ---
async def record_webinar(job):
    browser = None
    try:
        async with async_playwright() as p:
            logging.info(f"🎬 녹화 시작: {job.get('title') or '제목없음'}")
            video_dir = Path("videos")
            video_dir.mkdir(exist_ok=True)
            
            # 클라우드 실행을 위해 headless=True (로컬 테스트 시만 False)
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
           # context = await browser.new_context(viewport={'width': 1280, 'height': 720}, record_video_dir=str(video_dir))
            # 수정 후: 
             context = await browser.new_context(
             viewport={'width': 1280, 'height': 720},    # 브라우저가 보는 화면은 크게 유지 (글자 깨짐 방지)
             record_video_dir=str(video_dir),
             record_video_size={'width': 640, 'height': 360} # 👈 실제 저장되는 영상 크기를 360p로 줄여서 용량 절감
             )
            
            page = await context.new_page()
            await apply_stealth(page)

            await page.goto(job['webinar_url'], wait_until="networkidle")
            await asyncio.sleep(5)
            
            user_email = os.getenv("USER_EMAIL", "bot@daewoo.com")
            await handle_login(page, user_email)

            duration = int(job.get('duration_min', 1))
            for i in range(duration):
                await asyncio.sleep(60)
                progress = int((i + 1) / duration * 100)
                try: supabase.table("webinar_reservations").update({"progress": progress}).eq("id", job['id']).execute()
                except: pass
                logging.info(f"📹 진행 중: {i+1}/{duration}분")

            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                remote_name = f"webinars/{job['id']}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
                bucket.blob(remote_name).upload_from_filename(video_path)
                os.remove(video_path)
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info("✅ 저장 완료")
    except Exception as e:
        logging.error(f"❌ 오류: {e}")
        try: supabase.table("webinar_reservations").update({"status": "failed", "error_message": str(e)}).eq("id", job['id']).execute()
        except: pass

async def main():
    logging.info("🕵️ 감시병(v2.3.0) 가동 시작...")
    
    # 1. 구글 달력(GitHub Payload)에서 온 데이터가 있는지 확인
    cal_title = os.getenv("CALENDAR_TITLE")
    cal_url = os.getenv("CALENDAR_URL")

    if cal_title and cal_url:
        logging.info(f"📅 구글 달력 일정을 감지했습니다: {cal_title}")
        job = {
            "id": f"cal_{dt.datetime.now().strftime('%H%M%S')}",
            "title": cal_title,
            "webinar_url": cal_url,
            "duration_min": 60 # 기본 1시간 녹화 (필요시 조절)
        }
        await record_webinar(job)
        return # 달력 일정 처리 후 종료

    # 2. 달력 데이터가 없으면 기존처럼 Supabase 확인 (백업용)
    try:
        now_utc = dt.datetime.now(timezone.utc)
        res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
        
        for job in res.data:
            sch_time = pd.to_datetime(job['scheduled_at'], utc=True).to_pydatetime()
            if now_utc >= sch_time:
                locked = supabase.table("webinar_reservations").update({
                    "status": "running", "started_at": now_utc.isoformat()
                }).eq("id", job['id']).in_("status", ["pending", "trigger"]).execute()
                
                if locked.data:
                    await record_webinar(job)
    except Exception as e:
        logging.error(f"⚠️ Supabase 확인 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
