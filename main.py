import os
import json
import pytz
import pandas as pd
from datetime import datetime
from firebase_admin import credentials, storage, initialize_app, _apps
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- 1. 기본 환경 설정 ---
BUCKET_NAME = "webinar-recordings-plant-ti" 
KST = pytz.timezone('Asia/Seoul')

# 서비스 연결 초기화 (Firebase & Supabase)
if not _apps:
    info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"), strict=False)
    initialize_app(credentials.Certificate(info), {
        'storageBucket': f"{BUCKET_NAME}.appspot.com"
    })

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket = storage.bucket(BUCKET_NAME)

def run_recorder():
    now_utc = datetime.now(pytz.utc)
    print(f"[{datetime.now(KST)}] 녹화 스케줄러 가동 중...")

    # 대기 중인 예약 작업 조회
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger"]).execute()
    
    if not res.data:
        return

    for job in res.data:
        # DB의 예약 시간을 UTC로 변환하여 현재와 비교
        sched_utc = pd.to_datetime(job['scheduled_at']).astimezone(pytz.utc)
        
        if now_utc >= sched_utc:
            print(f"🎬 녹화 시작 대상: {job['title']}")
            # 상태 업데이트: 진행 중(running)
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job['id']).execute()
            
            try:
                with sync_playwright() as p:
                    # 브라우저 실행 (Headless 모드)
                    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
                    context = browser.new_context(
                        viewport={'width': 854, 'height': 480},
                        record_video_dir="/tmp/videos/",
                        record_video_size={'width': 854, 'height': 480}
                    )
                    page = context.new_page()
                    
                    # 사이트 접속
                    print(f"🔗 접속 URL: {job['webinar_url']}")
                    page.goto(job['webinar_url'], wait_until="networkidle", timeout=90000)
                    
                    # [지능형 3단계 시간차 클릭 로직] 사용자 지침 반영
                    # 이메일 주소 및 플레이 버튼을 5초 간격으로 총 3회 집요하게 클릭합니다.
                    targets = ["Play", "재생", "Join", "참가", "Confirm", "확인", "Enter", "입장", "OK"]
                    
                    for i in range(1, 4):
                        print(f"🖱️ {i}차 클릭 시도 중...")
                        page.wait_for_timeout(5000) # 5초 대기
                        
                        # (A) 이메일 입력창 주변의 확인 버튼 타격
                        try:
                            email_input = page.query_selector("input[type='email'], input[value*='@']")
                            if email_input:
                                btn = email_input.evaluate_handle("el => el.closest('div, form').querySelector('button, input[type=\"submit\"]')")
                                if btn: 
                                    btn.as_element().click()
                                    print("✅ 이메일 인접 확인 버튼 클릭 성공")
                        except: pass

                        # (B) 화면 내 텍스트 기반 버튼 탐색 및 클릭
                        for t in targets:
                            try:
                                btn = page.get_by_role("button", name=t, exact=False)
                                if btn.is_visible(): 
                                    btn.click()
                                    print(f"✅ 버튼 클릭 성공: {t}")
                            except: continue

                        # (C) 중앙 플레이 아이콘(SVG/삼각형) 강제 클릭
                        try:
                            page.click("svg, .vjs-big-play-button, .play-icon", timeout=3000)
                            print("✅ 플레이 아이콘(SVG) 클릭 시도 완료")
                        except: pass

                    # 지정된 시간만큼 녹화 유지
                    print(f"⏱️ 녹화 진행 중... ({job['duration_min']}분)")
                    page.wait_for_timeout(job['duration_min'] * 60 * 1000)
                    
                    # 영상 파일 저장 경로 획득 및 브라우저 종료
                    video_tmp_path = page.video.path()
                    browser.close()
                    
                    # Firebase Storage 업로드
                    blob = bucket.blob(f"recordings/{job['title']}_{job['id']}.webm")
                    blob.upload_from_filename(video_tmp_path)
                    
                    # [보안 지침 반영] make_public() 제거 및 직접 접근 URL 생성
                    # Google Cloud의 '균일한 버킷 수준 액세스' 설정에 맞춘 방식입니다.
                    video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/recordings/{job['title']}_{job['id']}.webm"
                    
                    # 성공 시 DB 업데이트
                    supabase.table("webinar_reservations").update({
                        "status": "completed",
                        "video_url": video_url,
                        "is_downloaded": False,
                        "failure_reason": None
                    }).eq("id", job['id']).execute()
                    print(f"✅ {job['title']} 녹화 및 업로드 완료")

            except Exception as e:
                # 실패 시 원인 기록
                error_msg = str(e)
                print(f"❌ 녹화 실패 원인 기록: {error_msg}")
                supabase.table("webinar_reservations").update({
                    "status": "error",
                    "failure_reason": error_msg
                }).eq("id", job['id']).execute()

if __name__ == "__main__":
    run_recorder()