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
        
        # main.py 하단 finally 부분을 아래와 같이 수정하세요.
        finally:
            print("5. 종료 절차를 시작합니다...")
            # 영상 파일 경로 확보
            video_path = await page.video.path() if page.video else None
            await context.close()
            await browser.close()
            
            if video_path and os.path.exists(video_path):
                # 복잡한 파일명을 'webinar_recording.webm'으로 변경하여 밖으로 꺼냅니다.
                import shutil
                shutil.move(video_path, "webinar_recording.webm")
                print(f"6. 녹화 완료! 파일 저장됨: webinar_recording.webm")
            else:
                print("6. 녹화 완료되었으나 영상 파일을 찾을 수 없습니다.")



if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    target_time = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    if not os.path.exists("recordings"):
        os.makedirs("recordings")
        print("알림: recordings 폴더를 생성했습니다.")
        
    asyncio.run(record_webinar(target_url, target_time))