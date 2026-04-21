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

# --- 4. [화면 1] 웨비나 녹화 예약 ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 예약")

    # 페이지 리런 시 시간 흐름 방지용 세션 설정
    if 'fixed_now' not in st.session_state:
        st.session_state.fixed_now = datetime.now(KST)

    with st.form("recording_form", clear_on_submit=False):
        st.markdown("### 📝 1. 웨비나 정보 입력")
        webinar_title = st.text_input("웨비나 명칭", placeholder="예: 수소 에너지 세미나")
        webinar_url = st.text_input("웨비나 URL", placeholder="https://...")
        
        st.markdown("### 🕒 2. 녹화 일정 설정 (개최지 기준)")
        selected_zone_name = st.selectbox("웨비나 개최 지역 (타임존)", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        
        # 개최지 기준의 현재 시각 계산
        now_at_location = st.session_state.fixed_now.astimezone(selected_timezone)
        st.caption(f"📍 현재 {selected_zone_name} 현지 시각은 **{now_at_location.strftime('%Y-%m-%d %H:%M')}** 입니다.")

        col1, col2 = st.columns(2)
        with col1:
            local_date = st.date_input("녹화 시작 날짜 (개최지 기준)", now_at_location.date())
        with col2:
            # 1분 단위 입력 가능
            local_time = st.time_input("녹화 시작 시각 (개최지 기준)", (now_at_location + timedelta(hours=1)).time(), step=60)
        
        duration = st.number_input("녹화 지속 시간 (분)", min_value=1, value=60, step=1)
        
        st.write("")
        confirm_check = st.checkbox("입력한 '개최지 기준 시각'이 정확함을 확인했습니다.")
        
        submit = st.form_submit_button("✅ 예약 확정 (클릭 시에만 저장됨)")
        
        if submit:
            if not confirm_check:
                st.warning("⚠️ 예약 확정을 위해 위 '확인했습니다' 체크박스를 먼저 클릭해 주세요.")
            elif not webinar_title or not webinar_url:
                st.error("⚠️ 웨비나 명칭과 URL을 모두 입력해 주세요.")
            else:
                # 사용자가 선택한 개최지의 날짜/시간 객체 생성
                chosen_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
                
                # 과거 예약 방지 (KST 기준 비교)
                if chosen_dt.astimezone(KST) < datetime.now(KST):
                    st.error("📍 현재보다 과거 시각으로는 예약할 수 없습니다.")
                else:
                    data = {
                        "title": webinar_title,
                        "webinar_url": webinar_url,
                        "scheduled_at": chosen_dt.isoformat(),
                        "duration_min": duration,
                        "status": "pending"
                    }
                    try:
                        supabase.table("webinar_reservations").insert(data).execute()
                        st.success(f"🎉 '{webinar_title}' 예약 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"DB 저장 오류: {e}")

    # --- 대기 목록 섹션 (사용자 요청 반영 수정) ---
    st.markdown("---")
    st.subheader("📝 예약 대기 목록")
    
    res = supabase.table("webinar_reservations").select("*").eq("status", "pending").order("scheduled_at").execute()
    
    if res.data:
        for item in res.data:
            # 1. 실제 녹화 예정 시각 (해당 국가 현지 시각)
            # 저장된 ISO 문자열에서 현지 시각 정보를 그대로 추출
            sched_dt = pd.to_datetime(item['scheduled_at'])
            local_sched_str = sched_dt.strftime('%Y-%m-%d %H:%M')
            
            # 2. 예약 신청 완료 시각 (한국 KST 기준)
            created_dt = pd.to_datetime(item.get('created_at'))
            kst_created = created_dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            # 참고용: 녹화 시각의 한국 시간 환산
            kst_sched_ref = sched_dt.astimezone(KST).strftime('%H:%M')

            # 목록 제목에 [현지 시간]을 표시하여 직관성 높임
            with st.expander(f"📌 [현지 {local_sched_str}] {item.get('title')}"):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**🔗 주소:** {item.get('webinar_url')}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        # [요청 반영] 실제 녹화 시작은 해당 나라 시간으로 표시
                        st.info(f"🎥 **실제 녹화 시작 (현지 시각)**\n{local_sched_str}")
                        st.caption(f"(한국 시간 기준: {kst_sched_ref})")
                    with col_b:
                        # [요청 반영] 신청 시각은 한국(KST) 시간으로 표시
                        st.success(f"📩 **예약 신청 완료 (서울 KST)**\n{kst_created}")
                    
                    st.markdown(f"⏱️ **지속 시간:** {item.get('duration_min')}분")
                with c2:
                    if st.button("🗑️ 삭제", key=f"del_{item.get('id')}", use_container_width=True):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("현재 대기 중인 예약이 없습니다.")

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