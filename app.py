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
    
    # [입력 폼] 입력값이 유지되도록 clear_on_submit=False 설정
    with st.form("recording_form", clear_on_submit=False):
        st.markdown("### 📝 녹화 일정 설정")
        
        # 1. 웨비나 명칭
        webinar_title = st.text_input(
            "웨비나 명칭", 
            placeholder="예: 수소 에너지 세미나",
            help="목록에 표시될 식별 이름입니다."
        )
        
        # 2. 웨비나 URL
        webinar_url = st.text_input(
            "웨비나 URL (필수)", 
            placeholder="https://..."
        )
        
        # 3. 시간대 선택
        selected_zone_name = st.selectbox("현지 시간대 선택 (해당 지역 기준)", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        
        # 현지 기준 현재 시각 계산 (기본값 설정용)
        now_local = datetime.now(selected_timezone)
        
        col1, col2 = st.columns(2)
        with col1:
            # 날짜 선택
            local_date = st.date_input("녹화 시작 날짜 (현지 기준)", now_local.date())
        with col2:
            # [수정] 1분 단위 입력 가능(step=60), 현재 시각과 겹치지 않게 기본값은 1시간 뒤로 설정
            local_time = st.time_input(
                "녹화 시작 시각 (현지 기준)", 
                value=(now_local + timedelta(hours=1)).time(),
                step=60, # 1분 단위로 조절 가능
                help="마우스 클릭이나 직접 입력을 통해 1분 단위로 시간을 설정하세요."
            )
        
        # 4. 녹화 지속 시간
        # [수정] step=1로 설정하여 1분 단위로 마음대로 입력 가능
        duration = st.number_input("녹화 지속 시간 (분 단위)", min_value=1, value=60, step=1)
        
        st.write("") 
        st.caption("※ 모든 입력 후 '✅ 예약 확정' 버튼을 클릭하세요. 입력값은 유지됩니다.")
        submit = st.form_submit_button("✅ 예약 확정")
        
        if submit:
            if not webinar_url or not webinar_title:
                st.error("⚠️ 명칭과 URL을 모두 입력해 주세요.")
            else:
                # [로직 수정] 사용자가 입력한 '현지 날짜/시간'을 해당 시간대의 객체로 만듦
                local_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
                
                data = {
                    "title": webinar_title,
                    "webinar_url": webinar_url,
                    "scheduled_at": local_dt.isoformat(), # 시차 정보(+04:00 등) 포함되어 저장됨
                    "duration_min": duration,
                    "status": "pending"
                }
                
                try:
                    supabase.table("webinar_reservations").insert(data).execute()
                    st.success(f"🎉 '{webinar_title}' 예약이 등록되었습니다. 아래 목록에서 확인하세요!")
                except Exception as e:
                    st.error(f"데이터베이스 저장 실패: {e}")

    # --- 대기 목록 섹션 ---
    st.markdown("---")
    st.subheader("📝 현재 예약 대기 목록 (한국 시간 기준)")
    
    res = supabase.table("webinar_reservations")\
        .select("*")\
        .eq("status", "pending")\
        .order("scheduled_at")\
        .execute()
    
    if res.data:
        for item in res.data:
            # [시간 계산 로직 강화]
            # 1. 예약된 녹화 시각 (Scheduled Time)
            # ISO 문자열에 포함된 시차 정보를 읽어 한국 시간(KST)으로 정확히 변환
            sched_dt = pd.to_datetime(item['scheduled_at'])
            kst_sched = sched_dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            # 2. 예약 신청 시각 (Created Time)
            # DB 생성 시각을 한국 시간으로 변환
            created_dt = pd.to_datetime(item.get('created_at'))
            kst_created = created_dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            # 현지 예약 시간 문자열 (사용자가 입력했던 시각 그대로)
            local_sched_display = sched_dt.strftime('%Y-%m-%d %H:%M')
            
            display_name = item.get('title') if item.get('title') else "이름 없음"
            
            with st.expander(f"📌 [녹화: {kst_sched}] {display_name}"):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**🔗 URL:** {item.get('webinar_url')}")
                    
                    # 시각 정보 카드 UI
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.info(f"📅 **실제 녹화 시작 (KST)**\n{kst_sched}")
                    with info_col2:
                        st.success(f"📩 **예약 신청 시각 (KST)**\n{kst_created}")
                    
                    st.caption(f"⏱️ 지속: {item.get('duration_min')}분 | 📍 현지 시각 기준: {local_sched_display}")
                
                with c2:
                    if st.button("🗑️ 삭제", key=f"del_{item.get('id')}"):
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