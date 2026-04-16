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

def check_and_run():
    """
    DB를 조회하여 정시 혹은 곧 시작할 녹화 작업을 찾아 실행합니다.
    """
    now_utc = datetime.now(pytz.utc)
    
    # [핵심 로직] 정시성 확보를 위한 시간 범위 설정
    # 1. 과거 2분 전 ~ 미래 12분 후 사이의 pending 작업을 찾습니다.
    # 2. 10분 주기 순찰이므로, 미래 작업을 미리 잡아 대기하게 함으로써 정각 시작을 보장합니다.
    start_range = (now_utc - timedelta(minutes=2)).isoformat()
    end_range = (now_utc + timedelta(minutes=12)).isoformat()
    
    print(f"--- 🔍 스케줄러 가동 ({now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC) ---")
    print(f"🔎 검색 범위: {start_range} ~ {end_range}")

    try:
        # 대기 중(pending)인 작업 중 범위 내에 있는 것들만 호출
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