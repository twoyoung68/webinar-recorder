import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone
import subprocess

# 설정 로드
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

def check_and_run():
    # 1. 현재 한국 시간 가져오기
    now = datetime.now(timezone.utc)
    print(f"현재 시각(UTC): {now}")

    # 2. 'pending' 상태이면서 시간이 지난(혹은 임박한) 예약 조회
    # 현재 시간 기준 5분 전부터 현재까지의 예약을 찾습니다.
    response = supabase.table("webinar_reservations") \
        .select("*") \
        .eq("status", "pending") \
        .lte("scheduled_at", now.isoformat()) \
        .execute()

    reservations = response.data

    if not reservations:
        print("대기 중인 예약이 없습니다.")
        return

    for res in reservations:
        res_id = res['id']
        target_url = res['webinar_url']
        duration = res['duration_min']

        print(f"녹화 시작 대상 발견: {target_url}")

        # 3. 상태를 'running'으로 변경 (중복 실행 방지)
        supabase.table("webinar_reservations").update({"status": "running"}).eq("id", res_id).execute()

        try:
            # 4. 실제 녹화 스크립트(main.py) 실행
            # subprocess를 사용해 이전에 만든 main.py를 호출합니다.
            print(f"main.py 실행 중... ({duration}분)")
            subprocess.run(["python", "main.py", target_url, str(duration)], check=True)

            # 5. 성공 시 상태 변경
            supabase.table("webinar_reservations").update({"status": "completed"}).eq("id", res_id).execute()
            print(f"성공: {res_id} 녹화 완료")
            
        except Exception as e:
            # 실패 시 상태 변경
            supabase.table("webinar_reservations").update({"status": "failed"}).eq("id", res_id).execute()
            print(f"실패: {res_id} 에러 발생 - {e}")

if __name__ == "__main__":
    check_and_run()