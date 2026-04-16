# [Section 1: 라이브러리 및 설정]
import asyncio
import os
import sys
import json
import firebase_admin
from firebase_admin import credentials, storage
from playwright.async_api import async_playwright
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# --- Firebase 초기화 ---
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_json:
        with open('temp_firebase_key.json', 'w') as f:
            f.write(firebase_json)
        cred = credentials.Certificate('temp_firebase_key.json')
    else:
        cred = credentials.Certificate('firebase_key.json')

    firebase_admin.initialize_app(cred, {
        'storageBucket': 'webinar-recorder.firebasestorage.app'
    })

# [Section 2: 보조 함수]
def upload_to_firebase(local_path, file_name):
    try:
        bucket = storage.bucket()
        blob = bucket.blob(file_name)
        blob.upload_from_filename(local_path)
        print(f"🚀 Firebase 업로드 성공: {file_name}")
        return True
    except Exception as e:
        print(f"❌ Firebase 업로드 실패: {e}")
        return False

def update_db_status(res_id, status_text):
    try:
        supabase.table("webinar_reservations").update({"status": status_text}).eq("id", res_id).execute()
        print(f"🔄 DB 상태 변경 완료: {status_text}")
    except Exception as e:
        print(f"⚠️ DB 상태 업데이트 실패: {e}")

# [Section 3: 녹화 수행 엔진 (스마트 클릭 로직 포함)]
async def record_webinar(res_id, target_url, duration_min):
    update_db_status(res_id, "running")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # [해상도 최적화] 기존 대비 절반 이하로 낮추어 용량과 부하를 줄입니다.
        # 640x360은 16:9 비율을 유지하면서도 매우 가벼운 설정입니다.
        context = await browser.new_context(
            viewport={'width': 640, 'height': 360},
            record_video_dir="temp_records/",
            record_video_size={'width': 640, 'height': 360},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            print(f"🔗 세미나 접속 시도: {target_url}")
            # 네트워크가 안정될 때까지 최대 90초 대기
            await page.goto(target_url, timeout=90000, wait_until="networkidle")
            
            # 1. 입장 전 새로고침 (세션 활성화 및 대기화면 탈출)
            print("⏳ 10초 대기 후 페이지를 새로고침합니다...")
            await asyncio.sleep(10)
            await page.reload(wait_until="networkidle")
            
            

            # 1. 유연한 매칭을 위한 키워드 리스트
            # 'has-text'를 사용하면 해당 문구가 포함만 되어 있어도 찾습니다.
            flexible_selectors = [
                "button:has-text('Join')",             # 'Join'이 들어간 모든 버튼
                "button:has-text('browser')",          # 브라우저에서 계속하기 등
                "button:has-text('web')",              # 웹에서 참여 등
                "button:has-text('Watch')",            # 시청하기 관련
                "button:has-text('시작')",             # 한국어 대응
                "button:has-text('참여')",             # 한국어 대응
                ".vjs-big-play-button",                # 비디오 플레이어 버튼 (클래스명)
                "button[aria-label*='Play']"           # Play 단어가 포함된 레이블
            ]
            
            print("🔍 지능형 버튼 탐색 시작...")
            for selector in flexible_selectors:
                try:
                    # 해당 키워드를 가진 요소가 화면에 나타날 때까지 최대 5초 대기
                    target = page.locator(selector).first # 여러 개면 첫 번째 것
                    if await target.is_visible(timeout=5000):
                        await target.click()
                        print(f"🎯 매칭 성공 및 클릭: {selector}")
                        await asyncio.sleep(5)
                        break
                except:
                    continue
            
            # 3. 최후의 수단: 화면 중앙 클릭 (오디오 활성화 및 강제 재생)
            print("🖱️ 화면 중앙을 클릭하여 최종 확인합니다.")
            await page.mouse.click(427, 240) 

            # 4. 녹화 대기
            print(f"🎥 녹화 중... ({duration_min}분 대기)")
            await asyncio.sleep(duration_min * 60)
            
        except Exception as e:
            print(f"⚠️ 녹화 도중 에러 발생: {e}")
            update_db_status(res_id, "error")
        
        finally:
            # 브라우저 종료 및 파일 확정
            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            # [Section 4: 마무리 작업 및 Firebase 업로드]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            final_name = f"webinar_{timestamp}.webm"
            
            if video_path and os.path.exists(video_path):
                success = upload_to_firebase(video_path, final_name)
                if success:
                    update_db_status(res_id, "completed")
                    if os.path.exists(video_path):
                        os.remove(video_path)
                else:
                    update_db_status(res_id, "failed")
            else:
                print("❌ 녹화 파일이 생성되지 않았습니다.")
                update_db_status(res_id, "error")

# [Section 5: 실행 메인 로직]
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python main.py [ID] [URL] [DURATION]")
        sys.exit(1)
        
    res_id = sys.argv[1]
    target_url = sys.argv[2]
    target_duration = int(sys.argv[3])
    
    if not os.path.exists("temp_records"):
        os.makedirs("temp_records")
        
    asyncio.run(record_webinar(res_id, target_url, target_duration))