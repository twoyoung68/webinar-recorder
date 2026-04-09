# [Section 1: 라이브러리 및 DB 연결 설정]
import os
from supabase import create_client
from datetime import datetime, timedelta
import pytz
import subprocess
from dotenv import load_dotenv

# 환경 변수 로드 (로컬 테스트 시 .env 참조 / GitHub 서버 시 Secrets 참조)
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# [Section 2: 예약 감시 및 실행 로직]
def check_and_run():
    now_utc = datetime.now(pytz.utc)
    # 10분 주기에 맞춰 탐색 범위를 12분 정도로 설정 (누락 방지)
    start_range = (now_utc - timedelta(minutes=12)).isoformat()
    end_range = (now_utc + timedelta(minutes=12)).isoformat()

    print(f"🔍 10분 주기 작업 감시 중... (기준 UTC: {now_utc.strftime('%H:%M')})")

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

    # [Section 3: 발견된 작업 실행]
    for job in all_jobs:
        print(f"🚀 녹화 대상 발견! ID: {job['id']}")
        # main.py를 실행하며 필요한 인자(ID, URL, 시간)를 전달
        try:
            subprocess.Popen([
                "python", "main.py", 
                str(job['id']), 
                job['webinar_url'], 
                str(job['duration_min'])
            ])
            print(f"🎬 녹화 로봇(main.py)이 호출되었습니다. (ID: {job['id']})")
        except Exception as e:
            print(f"❌ 실행 오류: {e}")

if __name__ == "__main__":
    check_and_run()