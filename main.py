import asyncio
import sys
import os
from playwright.async_api import async_playwright

async def record_webinar(url, duration_minutes):
    print("1. 브라우저를 준비하고 있습니다...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
            print("2. 브라우저 실행 성공!")
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                record_video_dir="recordings/",
                record_video_size={'width': 1280, 'height': 720}
            )
            
            page = await context.new_page()
            print(f"3. {url} 접속 시도 중...")
            
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"4. 접속 성공! {duration_minutes}분 동안 녹화합니다...")
            
            # 테스트를 위해 아주 짧게 대기 (초 단위)
            await asyncio.sleep(duration_minutes * 60)
            
        except Exception as e:
            print(f"!!! 에러 발생: {e}")
        
        finally:
            print("5. 종료 절차를 시작합니다...")
            await context.close()
            await browser.close()
            print("6. 녹화가 완료되었습니다. 파일을 확인하세요.")

if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    target_time = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    if not os.path.exists("recordings"):
        os.makedirs("recordings")
        print("알림: recordings 폴더를 생성했습니다.")
        
    asyncio.run(record_webinar(target_url, target_time))