import os
import subprocess
import pytz
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# [scheduler.py 수정 제안 - 범위 확장 버전]
def check_and_run():
    now_utc = datetime.now(pytz.utc)
    KST = pytz.timezone('Asia/Seoul')
    now_kst = now_utc.astimezone(KST)
    
    # [수정] 종료 범위를 12분에서 15분으로 늘려, 다음 순찰 전의 작업을 여유 있게 잡습니다.
    start_range = (now_utc - timedelta(minutes=5)).isoformat() # 과거 5분까지 허용
    end_range = (now_utc + timedelta(minutes=15)).isoformat() # 미래 15분까지 탐색
    
    print(f"--- 🔍 스케줄러 가동 (한국 시간: {now_kst.strftime('%H:%M:%S')}) ---")
    print(f"💡 탐색 예약 시간(KST): {(now_kst - timedelta(minutes=5)).strftime('%H:%M')} ~ {(now_kst + timedelta(minutes=15)).strftime('%H:%M')}")

    try:
        # DB에서 pending 상태인 작업을 가져옵니다.
        response = supabase.table("webinar_reservations") \
            .select("*") \
            .eq("status", "pending") \
            .gte("scheduled_at", start_range) \
            .lte("scheduled_at", end_range) \
            .execute()

        items = getattr(response, 'data', response)

        if not items:
            print("📭 현재 처리할 정시 녹화 작업이 없습니다.")
            return

        for item in items:
            job_id = item['id']
            url = item['webinar_url']
            duration = item['duration_min']
            sched_time_str = item['scheduled_at']
            
            # 예약 시간 객체 변환
            sched_time = datetime.fromisoformat(sched_time_str.replace('Z', '+00:00'))

            # [정시성 가드] 만약 로봇이 너무 늦게 깨어나서 예약 시간보다 5분 이상 지났다면?
            if now_utc > (sched_time + timedelta(minutes=5)):
                print(f"⏩ [SKIP] ID {job_id}: 예약 시간({sched_time})보다 5분 이상 지연되어 취소 처리합니다.")
                supabase.table("webinar_reservations").update({"status": "canceled"}).eq("id", job_id).execute()
                continue

            # 정상 범위라면 실행 시작
            print(f"🚀 [MATCH] 녹화 대상 발견! ID: {job_id} / 예약시간: {sched_time}")
            
            # 1. DB 상태를 'running'으로 즉시 변경 (중복 실행 방지)
            supabase.table("webinar_reservations").update({"status": "running"}).eq("id", job_id).execute()

            # 2. 녹화 로봇(main.py) 실행
            # URL과 녹화 시간을 인자로 전달합니다.
            try:
                print(f"🎬 녹화 프로세스 시작 (URL: {url}, Duration: {duration}분)")
                subprocess.run(["python", "main.py", url, str(duration), str(job_id)], check=True)
                print(f"✅ ID {job_id}: 녹화 및 업로드 프로세스 정상 종료")
            except subprocess.CalledProcessError as e:
                print(f"❌ ID {job_id}: 녹화 로봇 실행 중 에러 발생: {e}")
                supabase.table("webinar_reservations").update({"status": "failed"}).eq("id", job_id).execute()

    except Exception as e:
        print(f"❌ DB 조회 중 치명적 에러: {e}")

if __name__ == "__main__":
    check_and_run()