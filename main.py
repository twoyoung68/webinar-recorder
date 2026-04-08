# [Section 1: 라이브러리 로드 및 설정]
import asyncio
import os
import sys
import firebase_admin
from firebase_admin import credentials, storage
from playwright.async_api import async_playwright
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# 환경 변수 로드 (Supabase 접속용)
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Firebase 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'webinar-recorder.firebasestorage.app'
    })

# [Section 2: 핵심 보조 함수 - 업로드 및 상태 업데이트]
def upload_to_firebase(local_path, file_name):
    """녹화 파일을 Firebase Storage에 업로드"""
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
    """Supabase DB의 상태를 업데이트 (pending -> running -> completed)"""
    try:
        supabase.table("webinar_reservations").update({"status": status_text}).eq("id", res_id).execute()
        print(f"🔄 DB 상태 변경 완료: {status_text}")
    except Exception as e:
        print(f"⚠️ DB 상태 업데이트 실패: {e}")

# [Section 3: 녹화 수행 엔진 (480p 설정)]
async def record_webinar(res_id, target_url, duration_min):
    # 1. 녹화 시작 상태로 변경
    update_db_status(res_id, "running")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 480p(854x480) 해상도 및 녹화 설정
        context = await browser.new_context(
            viewport={'width': 854, 'height': 480},
            record_video_dir="temp_records/",
            record_video_size={'width': 854, 'height': 480}
        )
        
        page = await context.new_page()
        print(f"🔗 세미나 접속: {target_url}")
        
        try:
            # 타임아웃 1분 설정하여 접속
            await page.goto(target_url, timeout=60000)
            print(f"🎥 녹화 중... ({duration_min}분 대기)")
            await asyncio.sleep(duration_min * 60)
            
        except Exception as e:
            print(f"⚠️ 녹화 도중 에러 발생: {e}")
        
        finally:
            # 브라우저를 닫아야 영상 파일이 최종 확정됨
            await context.close()
            video_path = await page.video.path()
            await browser.close()
            
            # [Section 4: 파일명 생성 및 마무리 작업]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            final_name = f"webinar_{timestamp}.webm"
            
            if video_path and os.path.exists(video_path):
                # 2. Firebase 업로드
                success = upload_to_firebase(video_path, final_name)
                
                if success:
                    # 3. 업로드 성공 시 DB 상태를 'completed'로 변경
                    update_db_status(res_id, "completed")
                    # 로컬 임시 파일 삭제
                    if os.path.exists(video_path):
                        os.remove(video_path)
                else:
                    update_db_status(res_id, "failed")
            else:
                print("❌ 녹화 파일이 생성되지 않았습니다.")
                update_db_status(res_id, "error")

# [Section 5: 실행 메인 로직]
if __name__ == "__main__":
    # 인자값: python main.py [ID] [URL] [시간]
    # GitHub Actions나 서버에서 호출할 때 ID값을 같이 넘겨줘야 합니다.
    if len(sys.argv) < 4:
        print("사용법: python main.py [ID] [URL] [DURATION]")
        sys.exit(1)
        
    res_id = sys.argv[1]
    target_url = sys.argv[2]
    target_duration = int(sys.argv[3])
    
    if not os.path.exists("temp_records"):
        os.makedirs("temp_records")
        
    asyncio.run(record_webinar(res_id, target_url, target_duration))