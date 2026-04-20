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
    
    # 1. Firebase/Google Cloud 인증 정보 가져오기
    # 구글 클라우드 환경변수(FIREBASE_SERVICE_ACCOUNT 또는 FIREBASE_KEY)를 먼저 확인합니다.
    firebase_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT") or os.environ.get("FIREBASE_KEY")
    
    if firebase_json:
        try:
            # 환경변수에 저장된 JSON 문자열을 딕셔너리로 변환
            key_dict = json.loads(firebase_json)
            creds = service_account.Credentials.from_service_account_info(key_dict)
        except Exception as e:
            st.error(f"환경변수 인증 로드 실패: {e}")
            
    # 환경변수에 없으면 기존처럼 st.secrets 확인 (로컬 또는 Streamlit Cloud용)
    if creds is None and "FIREBASE_KEY" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
        except Exception as e:
            st.error(f"Secrets 인증 로드 실패: {e}")
            
    # 로컬 파일 확인 (파일이 실제로 있을 경우)
    elif creds is None and os.path.exists('firebase_key.json'):
        try:
            creds = service_account.Credentials.from_service_account_file('firebase_key.json')
        except Exception as e:
            st.error(f"로컬 파일 인증 로드 실패: {e}")

    if creds is None:
        st.error("보안 키를 찾을 수 없습니다. 구글 클라우드 콘솔의 환경 변수 설정을 확인해주세요.")
        st.stop()
        
    # 2. Supabase 설정 정보 가져오기
    # 환경변수에서 먼저 찾고, 없으면 st.secrets에서 찾습니다.
    supabase_url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("Supabase 설정 정보(URL/KEY)가 없습니다.")
        st.stop()

    # 클라이언트 생성
    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    supabase_client = create_client(supabase_url, supabase_key)
    
    return storage_client, supabase_client

# 연결 초기화
storage_client, supabase = init_all_connections()

# 버킷 설정
bucket_name = "webinar-recorder-plant-titeam.appspot.com"
bucket = storage_client.bucket(bucket_name)

# 파일 크기 변환 함수 (Bytes -> MB)
def get_size_format(b, factor=1024, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P"]:
        if b < factor:
            return f"{b:.2f}{unit}{suffix}"
        b /= factor

# --- 3. 사이드바 ---
with st.sidebar:
    st.title("🎥 Webinar Recorder")
    st.info(f"**현재 한국 시간(KST):**\n{datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    st.markdown("---")
    menu = st.radio("메뉴 이동", ["📅 웨비나 녹화 예약", "📂 녹화 내역 확인", "⚙️ 시스템 상태"])
    
    # [추가] 스토리지 간단 요약 정보
    st.markdown("---")
    st.subheader("💾 Storage Info")
    st.caption("Firebase Cloud Storage 사용 중")

# --- 4. [화면 1] 웨비나 녹화 예약 ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 예약")
    with st.form("recording_form"):
        webinar_url = st.text_input("웨비나 URL (필수)")
        selected_zone_name = st.selectbox("현지 시간대 선택", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        col1, col2 = st.columns(2)
        with col1: local_date = st.date_input("현지 날짜", datetime.now(selected_timezone))
        with col2: local_time = st.time_input("현지 시작 시간", datetime.now(selected_timezone))
        duration = st.number_input("녹화 지속 시간 (분)", min_value=1, value=60)
        submit = st.form_submit_button("✅ 예약 확정")
        
        if submit:
            if webinar_url:
                local_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
                data = {"webinar_url": webinar_url, "scheduled_at": local_dt.isoformat(), "duration_min": duration, "status": "pending"}
                supabase.table("webinar_reservations").insert(data).execute()
                st.success(f"🎉 예약 완료!")
                st.rerun()

    st.markdown("---")
    st.subheader("📝 현재 예약 대기 목록")
    res = supabase.table("webinar_reservations").select("*").eq("status", "pending").order("scheduled_at").execute()
    if res.data:
        for item in res.data:
            dt_obj = pd.to_datetime(item['scheduled_at'])
            display_time = dt_obj.astimezone(KST).strftime('%m/%d %H:%M')
            with st.expander(f"📌 {item.get('webinar_url')[:40]}... ({display_time} KST)"):
                c1, c2 = st.columns([4, 1])
                with c1: st.write(f"URL: {item.get('webinar_url')}\n\nTime: {item.get('duration_min')} min")
                with c2: 
                    if st.button("🗑️ 삭제", key=f"del_{item.get('id')}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()

# --- 5. [화면 2] 녹화 내역 확인 (업그레이드!) ---
elif menu == "📂 녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    
    try:
        blobs = list(bucket.list_blobs(prefix="recordings/"))
        # 파일 확장자 필터링 및 최신순 정렬
        valid_files = sorted([b for b in blobs if b.name.endswith((".webm", ".mp4"))], 
                            key=lambda x: x.updated, reverse=True)
        
        if not valid_files:
            st.info("저장된 영상이 없습니다.")
        else:
            # 전체 사용량 계산
            total_size = sum([b.size for b in valid_files])
            st.write(f"📊 **총 {len(valid_files)}개의 파일** (합계 용량: {get_size_format(total_size)})")
            st.markdown("---")

            for blob in valid_files:
                # 파일 정보 추출
                file_name = blob.name.split('/')[-1]
                file_size = get_size_format(blob.size)
                # 구글 스토리지 시간(UTC)을 한국 시간으로 변환
                upload_time = blob.updated.astimezone(KST).strftime('%Y-%m-%d %H:%M')
                
                # 카드형 UI 구성
                with st.container(border=True):
                    col_icon, col_txt, col_btn = st.columns([1, 6, 2])
                    with col_icon:
                        st.markdown("### 🎥")
                    with col_txt:
                        st.markdown(f"**파일명:** {file_name}")
                        st.caption(f"💾 용량: {file_size} | 🕒 업로드: {upload_time}")
                    with col_btn:
                        # 다운로드 링크 생성
                        url = blob.generate_signed_url(expiration=timedelta(hours=1))
                        st.link_button("⬇️ 다운로드", url, use_container_width=True)
                        # 삭제 기능 추가 (선택 사항)
                        if st.button("🗑️ 삭제", key=f"file_del_{blob.name}", use_container_width=True):
                            blob.delete()
                            st.rerun()
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

# --- 6. [화면 3] 시스템 상태 ---
elif menu == "⚙️ 시스템 상태":
    st.header("⚙️ 시스템 상태")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("DB Status", "Connected", "Supabase")
    with col2:
        st.metric("Storage Status", "Connected", "Firebase")
    st.info("자동 녹화 봇은 Google Cloud Run 환경에서 작동 중입니다.")
