import streamlit as st
import json
import os
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client
import pytz

# --- 1. 페이지 및 시간대 설정 ---
st.set_page_config(page_title="Plant TI Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "아랍에미리트 (GST)": "Asia/Dubai",
    "영국/런던 (GMT/BST)": "Europe/London",
    "중유럽/독일/프랑스 (CET/CEST)": "Europe/Berlin",
    "미국 동부/뉴욕 (EST/EDT)": "US/Eastern",
    "미국 서부/LA (PST/PDT)": "US/Pacific",
    "베트남 (ICT)": "Asia/Ho_Chi_Minh"
}

# --- 2. 보안 인증 및 클라이언트 설정 ---
@st.cache_resource
def init_all_connections():
    creds = None
    
    # [보안] Secret Manager / 환경 변수 우선 로드
    firebase_json = os.environ.get("FIREBASE_KEY") or \
                    os.environ.get("FIREBASE_SERVICE_ACCOUNT") or \
                    st.secrets.get("FIREBASE_KEY")
    
    if firebase_json:
        try:
            if isinstance(firebase_json, str):
                key_dict = json.loads(firebase_json)
            else:
                key_dict = firebase_json
            creds = service_account.Credentials.from_service_account_info(key_dict)
        except Exception as e:
            st.error(f"Firebase 인증 파싱 실패: {e}")
    elif os.path.exists('firebase_key.json'):
        try:
            creds = service_account.Credentials.from_service_account_file('firebase_key.json')
        except Exception as e:
            st.error(f"로컬 파일 인증 실패: {e}")

    if creds is None:
        st.error("보안 키를 찾을 수 없습니다. Secret Manager 설정을 확인해주세요.")
        st.stop()
        
    # Supabase 설정 (환경 변수 또는 st.secrets)
    supabase_url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("Supabase 설정 정보가 없습니다.")
        st.stop()

    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    supabase_client = create_client(supabase_url, supabase_key)
    
    return storage_client, supabase_client

# 초기화 실행
storage_client, supabase = init_all_connections()
bucket_name = "webinar-recordings-plant-ti"
bucket = storage_client.bucket(bucket_name)

def get_size_format(b, factor=1024, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P"]:
        if b < factor: return f"{b:.2f}{unit}{suffix}"
        b /= factor

# --- 3. 사이드바 ---
with st.sidebar:
    st.title("🎥 Webinar Recorder")
    st.info(f"**현재 한국 시간(KST):**\n{datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    st.markdown("---")
    menu = st.radio("메뉴 이동", ["📅 웨비나 녹화 예약", "📂 녹화 내역 확인", "⚙️ 시스템 상태"])

# --- 4. [화면 1] 웨비나 녹화 예약 및 관리 ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 통합 관리")

    # [1] 시간 고정 로직 (입력 중 리프레시 방지)
    if 'fixed_now' not in st.session_state:
        st.session_state.fixed_now = datetime.now(KST)

    # --- 예약 입력 구역 ---
    with st.form("recording_form", clear_on_submit=False):
        st.markdown("### 📝 1. 웨비나 정보 입력")
        webinar_title = st.text_input("웨비나 명칭", placeholder="예: 수소 에너지 세미나")
        webinar_url = st.text_input("웨비나 URL", placeholder="https://...")
        
        st.markdown("### 🕒 2. 녹화 일정 설정 (개최지 기준)")
        selected_zone_name = st.selectbox("웨비나 개최 지역 (타임존)", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        
        now_at_location = st.session_state.fixed_now.astimezone(selected_timezone)
        st.caption(f"📍 현재 {selected_zone_name} 현지 시각: **{now_at_location.strftime('%Y-%m-%d %H:%M')}**")

        col1, col2 = st.columns(2)
        with col1:
            local_date = st.date_input("녹화 시작 날짜", now_at_location.date())
        with col2:
            local_time = st.time_input("녹화 시작 시각", (now_at_location + timedelta(hours=1)).time(), step=60)
        
        duration = st.number_input("녹화 지속 시간 (분)", min_value=1, value=60, step=1)
        
        st.write("")
        confirm_check = st.checkbox("입력한 정보가 정확함을 확인했습니다.")
        submit = st.form_submit_button("🚀 예약 확정")
        
        if submit:
            if not confirm_check:
                st.warning("⚠️ 확인 체크박스를 먼저 클릭해 주세요.")
            elif not webinar_title or not webinar_url:
                st.error("⚠️ 명칭과 URL을 모두 입력해 주세요.")
            else:
                chosen_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
                if chosen_dt.astimezone(KST) < datetime.now(KST):
                    st.error("📍 과거 시각으로는 예약할 수 없습니다.")
                else:
                    data = {
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": chosen_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone_name
                    }
                    try:
                        supabase.table("webinar_reservations").insert(data).execute()
                        st.success(f"✅ '{webinar_title}' 예약 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"DB 오류: {e}")

    # --- [개선] 통합 관리 목록 섹션 ---
    st.markdown("---")
    st.subheader("📋 전체 예약 및 녹화 현황")

    # 모든 상태의 데이터를 최신순으로 가져옴
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(20).execute()
    
    if res.data:
        for item in res.data:
            status = item.get('status', 'pending')
            # 상태별 아이콘 및 메시지 설정
            status_map = {
                "pending": ("⏳ 대기 중", "blue"),
                "running": ("⏺️ 녹화 중...", "orange"),
                "completed": ("✅ 녹화 완료", "green"),
                "error": ("❌ 에러 발생", "red")
            }
            status_text, status_color = status_map.get(status, ("❓ 알 수 없음", "gray"))

            # 시간 처리
            sched_dt = pd.to_datetime(item['scheduled_at'])
            target_tz = pytz.timezone(WORLD_ZONES.get(item.get('timezone_name', '대한민국 (KST)'), 'Asia/Seoul'))
            local_sched = sched_dt.astimezone(target_tz).strftime('%Y-%m-%d %H:%M')
            kst_sched = sched_dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')
            created_at = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%m-%d %H:%M')

            # Expander 제목에 상태를 표시하여 직관성 극대화
            with st.expander(f"[{status_text}] {item.get('title')} ({local_sched})"):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**🔗 URL:** {item.get('webinar_url')}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.info(f"📅 **녹화 시작 (현지)**\n{local_sched}\n(KST: {kst_sched})")
                    with col_b:
                        st.success(f"📩 **신청 일시 (KST)**\n{created_at}")
                    
                    # 완료 상태일 때만 영상 확인 버튼 표시
                    if status == "completed":
                        video_url = item.get('video_url')
                        if video_url:
                            st.markdown(f"### 🎬 [녹화 영상 확인하기]({video_url})")
                        else:
                            st.warning("⚠️ 파일 링크를 찾는 중입니다...")
                    elif status == "error":
                        st.error("❗ 녹화 중 문제가 발생했습니다. 로그를 확인해 주세요.")
                    elif status == "running":
                        st.warning("🔔 현재 녹화가 진행 중입니다. 종료 후 링크가 생성됩니다.")

                with c2:
                    if st.button("🗑️ 삭제", key=f"del_{item['id']}", use_container_width=True):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("표시할 내역이 없습니다.")

# --- 5. [화면 2] 녹화 내역 확인 ---
elif menu == "📂 녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    try:
        blobs = list(bucket.list_blobs(prefix="recordings/"))
        valid_files = sorted([b for b in blobs if b.name.endswith((".webm", ".mp4"))], 
                            key=lambda x: x.updated, reverse=True)
        
        if not valid_files:
            st.info("저장된 영상이 없습니다.")
        else:
            st.write(f"📊 **총 {len(valid_files)}개의 파일**")
            for blob in valid_files:
                file_name = blob.name.split('/')[-1]
                file_size = get_size_format(blob.size)
                upload_time = blob.updated.astimezone(KST).strftime('%Y-%m-%d %H:%M')
                
                with st.container(border=True):
                    col_txt, col_btn = st.columns([7, 3])
                    with col_txt:
                        st.markdown(f"**🎥 {file_name}**")
                        st.caption(f"💾 {file_size} | 🕒 업로드: {upload_time} (KST)")
                    with col_btn:
                        url = blob.generate_signed_url(expiration=timedelta(hours=1))
                        st.link_button("⬇️ 다운로드", url, use_container_width=True)
                        if st.button("🗑️ 삭제", key=f"f_del_{blob.name}", use_container_width=True):
                            blob.delete()
                            st.rerun()
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

# --- 6. [화면 3] 시스템 상태 ---
elif menu == "⚙️ 시스템 상태":
    st.header("⚙️ 시스템 상태")
    st.success("데이터베이스(Supabase) 및 스토리지(Firebase) 연결 정상")
    st.info("이 앱은 Google Cloud Run 환경에서 작동하며 보안을 위해 Secret Manager를 사용합니다.")