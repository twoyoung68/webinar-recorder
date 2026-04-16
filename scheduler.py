# [Section 1: 라이브러리 및 DB 연결 설정]
import os
from supabase import create_client
from datetime import datetime, timedelta
import pytz
import subprocess
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# [Section 2: 예약 감시 및 실행 로직]
def check_and_run():
    now_utc = datetime.now(pytz.utc)
    # 실행 범위를 현재 시간 기준 앞뒤로 설정
    start_range = (now_utc - timedelta(minutes=15)).isoformat()
    end_range = (now_utc + timedelta(minutes=5)).isoformat()

    print(f"🔍 작업 감시 중... (기준 UTC: {now_utc.strftime('%Y-%m-%d %H:%M')})")

    # A. 'pending' 상태이면서 예약 시간이 임박한 작업 조회
    res = supabase.table("webinar_reservations") \
        .select("*") \
        .eq("status", "pending") \
        .gte("scheduled_at", start_range) \
        .lte("scheduled_at", end_range) \
        .execute()

    # B. 'trigger'(즉시 실행) 요청된 작업 조회
    trigger_res = supabase.table("webinar_reservations") \
        .select("*") \
        .eq("status", "trigger") \
        .execute()

    all_jobs = res.data + trigger_res.data

    if not all_jobs:
        print("✅ 현재 실행할 작업이 없습니다.")
        return

 # [Section 3: 발견된 작업 실행 및 상태 업데이트]
    for job in all_jobs:
        job_id = job['id']
        print(f"🚀 녹화 대상 발견! ID: {job_id}")
        
        try:
            # 1. DB 상태를 'running'으로 변경
            supabase.table("webinar_reservations") \
                .update({"status": "running"}) \
                .eq("id", job_id) \
                .execute()
            print(f"🔄 ID {job_id} 상태를 'running'으로 변경했습니다.")

            # [수정 포인트] Popen 대신 run을 사용하거나, .wait()를 추가하여 
            # 녹화가 끝날 때까지 GitHub Actions 세션이 유지되게 합니다.
            print(f"🎬 녹화 로봇(main.py)을 실행합니다. 녹화 완료까지 대기합니다...")
            
            subprocess.run([
                "python", "main.py", 
                str(job_id), 
                job['webinar_url'], 
                str(job['duration_min'])
            ], check=True) # 녹화가 끝날 때까지 여기서 기다립니다.
            
            print(f"✅ ID {job_id} 녹화 프로세스가 정상적으로 종료되었습니다.")
            
        except Exception as e:
            print(f"❌ 실행 오류 (ID: {job_id}): {e}")
            supabase.table("webinar_reservations").update({"status": "error"}).eq("id", job_id).execute()
if __name__ == "__main__":
    check_and_run()