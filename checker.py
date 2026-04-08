import os
import subprocess
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 파일 또는 GitHub Secrets에서 읽어옴)
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("⚠️ 에러: SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")
    exit(1)

supabase = create_client(url, key)

def check_and_run():
    # 2. 현재 시각을 UTC 기준으로 가져오기 (가장 정확한 비교 방법)
    # 9시간 오차 문제를 방지하기 위해 서버와 DB는 항상 UTC로 대화합니다.
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    print(f"🔍 체크 시작 (현재 UTC 시각): {now_iso}")

    try:
        # 3. 'pending' 상태이면서 시작 시간이 현재보다 과거(또는 현재)인 예약 조회
        # .lte("scheduled_at", now_iso) -> 예정 시간이 지금보다 작거나 같은 것들
        response = supabase.table("webinar_reservations") \
            .select("*") \
            .eq("status", "pending") \
            .lte("scheduled_at", now_iso) \
            .execute()

        reservations = response.data

        if not reservations:
            print("📭 대기 중인 예약이 없습니다.")
            return

        for res in reservations:
            res_id = res['id']
            target_url = res['webinar_url']
            duration = str(res['duration_min'])
            
            print(f"🚀 녹화 대상 발견! ID: {res_id} / URL: {target_url}")

            # 4. 중복 실행 방지를 위해 즉시 상태를 'running'으로 변경
            supabase.table("webinar_reservations") \
                .update({"status": "running"}) \
                .eq("id", res_id) \
                .execute()

            try:
                # 5. 실제 녹화 스크립트(main.py) 실행
                # main.py에 URL과 지속 시간을 인자로 전달합니다.
                print(f"🎬 녹화 프로세스 시작... ({duration}분)")
                subprocess.run(["python", "main.py", target_url, duration], check=True)

                # 6. 녹화 성공 시 상태를 'completed'로 업데이트
                supabase.table("webinar_reservations") \
                    .update({"status": "completed"}) \
                    .eq("id", res_id) \
                    .execute()
                print(f"✅ 녹화 완료 및 상태 업데이트 성공 (ID: {res_id})")

            except subprocess.CalledProcessError as e:
                # 녹화 프로그램 실행 중 에러 발생 시
                supabase.table("webinar_reservations") \
                    .update({"status": "failed"}) \
                    .eq("id", res_id) \
                    .execute()
                print(f"❌ 녹화 실패 (ID: {res_id}): {e}")

    except Exception as e:
        print(f"❌ 데이터베이스 조회 중 에러 발생: {e}")

if __name__ == "__main__":
    check_and_run()