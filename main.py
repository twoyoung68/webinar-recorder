# [Section 1: 라이브러리 로드 및 Firebase 초기화 수정]
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

# --- Firebase 초기화 로직 ---
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

# [Section 3: 녹화 수행 엔진 (입장 알고리즘 보강)]
async def record_webinar(res_id, target_url, duration_min):
    update_db_status(res_id, "running")
    
    async with async_playwright() as p:
        # 브라우저 실행 (가상 디스플레이 설정 포함)
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport={'width': 854, 'height': 480},
            record_video_dir="temp_records/",
            record_video_size={'width': 854, 'height': 480},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            print(f"🔗 세미나 접속 시도: {target_url}")
            await page.goto(target_url, timeout=90000, wait_until="networkidle")
            
            # [추가] 1. 입장 전 새로고침 로직 (세션 활성화)
            print("⏳ 10초 대기 후 페이지를 새로고침하여 입장을 확인합니다...")
            await asyncio.sleep(10)
            await page.reload(wait_until="networkidle")
            
            # [추가] 2. 범용 입장 버튼 클릭 알고리즘
            # GoToWebinar 및 일반 웨비나 사이트들의 '참여' 버튼 패턴들
            selectors = [
                "text='웹에서 참여'", "text='Join on the web'", 
                "text='Listen Only'", "text='무료로 참여'",
                "button:has-text('Join')", ".join-button"
            ]
            
            for selector in selectors:
                try:
                    # 각 버튼을 최대 5초간 찾아보고 있으면 클릭
                    btn = page.locator(selector)
                    if await btn.is_visible(timeout=5000):
                        await btn.click()
                        print(f"✅ 입장 버튼 클릭 성공: {selector}")
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            # [추가] 3. 오디오 활성화 및 포커스를 위한 화면 중앙 클릭
            print("🖱️ 화면 중앙을 클릭하여 오디오를 활성화합니다.")
            await page.mouse.click(427, 240) 

            # 4. 실제 녹화 대기
            print(f"🎥 녹화 시작... ({duration_min}분 대기)")
            await asyncio.sleep(duration_min * 60)
            
        except Exception as e:
            print(f"⚠️ 녹화 도중 에러 발생: {e}")
            update_db_status(res_id, "error") # 에러 시 즉시 반영
        
        finally:
            # 브라우저 종료 및 파일 확정
            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            # [Section 4: 마무리 작업]
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
                # 이미 에러가 발생했다면 위에서 처리되었겠지만, 안전을 위해 한 번 더 확인
                current_data = supabase.table("webinar_reservations").select("status").eq("id", res_id).execute()
                if current_data.data[0]['status'] != 'completed':
                    update_db_status(res_id, "error")

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