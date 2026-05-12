# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.5.0 (Safety First Edition)
# DESCRIPTION: 로컬 연결 vs 클라우드 자동 시도 듀얼 엔진
# ==========================================

import os
import asyncio
import logging
import random
import datetime as dt
from pathlib import Path
from playwright.async_api import async_playwright
import playwright_stealth

# (서비스 초기화 로직 생략 - v2.4.2와 동일)

async def record_webinar(job):
    async with async_playwright() as p:
        logging.info(f"🎬 녹화 세션 시작: {job['title']} (Mode: {job['rec_mode']})")
        
        try:
            if job['rec_mode'] == 'local':
                # [로컬 모드] 이미 열린 크롬에 접속
                logging.info("🖥️ 로컬 크롬(9222 포트) 연결을 시도합니다...")
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.pages[0]
            else:
                # [클라우드 모드] 새 브라우저 실행 (쿠키 없음)
                logging.info("☁️ 클라우드 자동 접속을 시도합니다...")
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1280, 'height': 720})
                page = await context.new_page()
                await page.goto(job['webinar_url'], wait_until="networkidle")

            # 공통: 플레이 버튼 클릭 시도 및 녹화 루프
            await asyncio.sleep(5) 
            await page.mouse.click(640, 360) # 중앙 클릭
            
            duration = int(job.get('duration_min', 60))
            for i in range(duration):
                await asyncio.sleep(60)
                logging.info(f"📹 촬영 중... {i+1}/{duration} 분")

            # (파일 업로드 로직 생략 - v2.4.2와 동일)
            
        except Exception as e:
            logging.error(f"❌ 녹화 실패: {e}")
