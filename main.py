import os
import json
import pytz
import pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 기본 환경 설정 ---
BUCKET_NAME = "webinar-recordings-plant-ti" 
KST = pytz.timezone('Asia/Seoul')

if not _apps:
    info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"), strict=False)
    initialize_app(credentials.Certificate(info), {'storageBucket': f"{BUCKET_NAME}.appspot.com"})

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = storage.bucket(BUCKET_NAME)

def run_recorder():
    now_utc = datetime.now(pytz.utc)
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    
    for job in res.data:
        sched_utc = pd.to_datetime(job['scheduled_at']).astimezone(pytz.utc)
        
        if now_utc >= sched_utc:
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job['id']).execute()
            # 기본 실패 사유 설정
            failure_reason = "알 수 없는 시스템 오류"
            
            try:
                with sync_playwright() as p:
                    # 봇 감지 회피용 스텔스 설정
                    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    context = browser.new_context(user_agent=user_agent, viewport={'width': 1280, 'height': 720}, record_video_dir="/tmp/videos/")
                    page = context.new_page()
                    
                    # 1. 사이트 접속 및 초기 로딩 대기 (사용자 제보: 5초 이상 소요)
                    print(f"🔗 접속 시도: {job['webinar_url']}")
                    try:
                        page.goto(job['webinar_url'], wait_until="networkidle", timeout=120000)
                        print("⏳ 화면 로딩 대기 (10초)...")
                        page.wait_for_timeout(10000) # 넉넉하게 10초 대기
                    except PlaywrightTimeoutError:
                        failure_reason = "접속 실패: 사이트가 120초 이내에 응답하지 않았습니다 (네트워크 타임아웃)."
                        raise Exception(failure_reason)

                    # 2. 로봇 감지 여부 선제 확인
                    if "captcha" in page.content().lower() or "forbidden" in page.content().lower():
                        failure_reason = "로봇 감지: 사이트 보안 정책이 자동 접속을 차단했습니다."
                        raise Exception(failure_reason)

                    # 3. [강화] 중앙 삼각형 플레이 버튼 정밀 클릭 로직
                    click_success = False
                    # 사용자 제보: 가운데 삼각형 모양 아이콘 타겟팅
                    play_selectors = [
                        "button[aria-label*='Play']", 
                        "button[aria-label*='재생']",
                        ".vjs-big-play-button",  # Video.js 표준 버튼
                        "svg polygon",           # 삼각형 모양 아이콘 직접 선택
                        ".play-icon", 
                        "button:has-text('Join')", 
                        "button:has-text('Confirm')"
                    ]
                    
                    for i in range(1, 4):
                        print(f"🖱️ {i}차 클릭 시도 중...")
                        
                        # (A) 중앙 삼각형 아이콘 직접 좌표 클릭 시도 (가장 확실함)
                        try:
                            # 화면 중앙 좌표 계산
                            viewport = page.viewport_size
                            page.mouse.click(viewport['width'] / 2, viewport['height'] / 2)
                            print("✅ 화면 중앙 좌표 클릭 수행")
                        except: pass

                        # (B) 셀렉터 기반 클릭
                        for selector in play_selectors:
                            try:
                                target = page.query_selector(selector)
                                if target and target.is_visible():
                                    target.click()
                                    print(f"✅ 버튼 클릭 성공: {selector}")
                                    click_success = True
                                    break
                            except: continue
                        
                        if click_success: break
                        page.wait_for_timeout(5000) # 실패 시 5초 후 재시도

                    if not click_success:
                        print("⚠️ 경고: 플레이 버튼을 찾지 못했습니다. 화면이 멈춰있을 수 있습니다.")
                        # 여기서 중단하지 않고 일단 녹화는 진행 (증거 수집용)

                    # 4. 녹화 진행
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    
                    video_path = page.video.path()
                    browser.close()
                    
                    # Firebase 업로드 및 성공 보고
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(video_path)
                    video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/recordings/{job['title']}_{job['id']}.webm"
                    
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": video_url,
                        "failure_reason": "녹화 완료 (클릭 성공 여부: " + ("성공" if click_success else "실패/미확인") + ")"
                    }).eq("id", job['id']).execute()

            except Exception as e:
                err_msg = str(e)
                print(f"❌ 녹화 중단: {err_msg}")
                supabase.table("webinar_reservations").update({
                    "status": "error",
                    "failure_reason": err_msg
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()