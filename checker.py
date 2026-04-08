import os
import subprocess
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

# 1. 환경 변수 로드 및 DB 연결
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

def check_and_run():
    # 현재 시간을 UTC 기준으로 가져오기
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    
    print(f"🔍 체크 시작 (현재 UTC 시각): {now_iso}")

    try:
        # 대기 중(pending)이면서 시작 시간이 된 예약 조회
        response = supabase.table("webinar_reservations") \
            .select("*") \
            .eq("status", "pending") \
            .lte("scheduled_at", now_iso) \
            .execute()

        reservations = response.data

        if not reservations:
            print("📭 현재 처리할 예약이 없습니다.")
            return

        for res in reservations:
            res_id = res['id']
            target_url = res['webinar_url']
            duration = str(res['duration_min'])
            
            print(f"🚀 녹화 발견! ID: {res_id} / URL: {target_url}")

            # 2. 중복 실행 방지를 위해 상태를 'running'으로 변경
            supabase.table("webinar_reservations") \
                .update({"status": "running"}) \
                .eq("id", res_id) \
                .execute()

            try:
                # 3. 실제 녹화(main.py) 실행
                # 파일은 main.py가 스스로 'webinar_recording.webm'으로 저장합니다.
                print(f"🎬 녹화 프로세스 시작... ({duration}분)")
                subprocess.run(["python", "main.py", target_url, duration], check=True)

                # 4. 녹화 성공 시 DB 상태만 'completed'로 업데이트
                supabase.table("webinar_reservations") \
                    .update({"status": "completed"}) \
                    .eq("id", res_id) \
                    .execute()
                print(f"✅ 녹화 로직 종료 (ID: {res_id})")

            except subprocess.CalledProcessError as e:
                # 녹화 실패 시 상태 변경
                supabase.table("webinar_reservations") \
                    .update({"status": "failed"}) \
                    .eq("id", res_id) \
                    .execute()
                print(f"❌ 녹화 실패 (ID: {res_id}): {e}")

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    check_and_run()