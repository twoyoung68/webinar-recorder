# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v2.5.1 (Engine Edition)
# DESCRIPTION: 듀얼 모드 녹화 수행 엔진
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
    logging.error(f"라이브러리 로드 실패: {e}")
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

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 녹화 세션 시작: {job['title']} ({job['rec_mode']})")
        video_dir = Path("videos")
        video_dir.mkdir(exist_ok=True)
        
        try:
            if job['rec_mode'] == 'local':
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0]
                logging.info("🖥️ 로컬 크롬 연결 성공")
            else:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1280, 'height': 720},
                                                   record_video_dir=str(video_dir))
                page = await context.new_page()
                await page.goto(job['webinar_url'], wait_until="networkidle")
                logging.info("☁️ 클라우드 접속 성공")

            # 플레이 버튼 클릭
            await asyncio.sleep(8)
            await page.mouse.click(640, 360) 
            
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
                supabase.table("webinar_reservations").update({"status": "completed", "video_url": remote_name}).eq("id", job['id']).execute()
                logging.info(f"✅ 업로드 완료")

        except Exception as e:
            logging.error(f"❌ 에러: {e}")

async def main():
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    for job in res.data:
        await record_webinar(job)

if __name__ == "__main__":
    asyncio.run(main())
