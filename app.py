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

# 주요 프로젝트 거점 시간대 정의
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
    # 1순위: Streamlit Secrets
    if "FIREBASE_KEY" in st.secrets:
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
    # 2순위: 로컬 파일
    elif os.path.exists('firebase_key.json'):
        creds = service_account.Credentials.from_service_account_file('firebase_key.json')

    if creds is None:
        st.error("보안 키(Secrets 또는 JSON 파일)가 없습니다. 설정을 확인해 주세요.")
        st.stop()
        
    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    
    # Supabase 연결
    supabase_client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    return storage_client, supabase_client

storage_client, supabase = init_all_connections()
bucket = storage_client.bucket("webinar-recorder-plant-titeam.appspot.com")

# --- 3. 사이드바 (정보창 및 메뉴) ---
with st.sidebar:
    st.title("🎥 Webinar Recorder")
    st.info(f"**현재 한국 시간(KST):**\n{datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    
    st.markdown("---")
    menu = st.radio("메뉴 이동", ["📅 웨비나 녹화 예약", "📂 녹화 내역 확인", "⚙️ 시스템 상태"])
    
    st.markdown("---")
    st.subheader("📊 시스템 정보")
    st.write(f"**Target Project:** Gemini API (Plant TI)")
    st.write(f"**Storage:** Firebase Cloud Storage")
    st.caption("Developed by Plant TI Team")

# --- 4. [화면 1] 웨비나 녹화 예약 (업그레이드 버전) ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 예약")
    
    with st.form("recording_form"):
        title = st.text_input("세미나 제목", placeholder="예: 2026 SMR 기술 전략 세미나")
        webinar_url = st.text_input("웨비나 URL")
        
        st.markdown("#### 🌍 시간대 설정")
        # 1. 현지 시간대 선택 옵션 추가
        selected_zone_name = st.selectbox("어느 국가의 현지 시간으로 입력하시겠습니까?", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        
        col1, col2 = st.columns(2)
        with col1:
            local_date = st.date_input("현지 날짜", datetime.now(selected_timezone))
        with col2:
            local_time = st.time_input("현지 시작 시간", datetime.now(selected_timezone))
            
        duration = st.number_input("녹화 지속 시간 (분)", min_value=10, max_value=300, value=60)
        
        st.markdown("---")
        submit = st.form_submit_button("✅ 예약 확정")
        
        if submit:
            # 2. 입력받은 날짜/시간을 해당 국가의 시간대로 설정
            local_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
            
            # 3. 이를 한국 시간(KST)으로 자동 변환
            scheduled_kst = local_dt.astimezone(KST)
            scheduled_iso = scheduled_kst.isoformat()
            
            data = {
                "title": title,
                "url": webinar_url,
                "scheduled_at": scheduled_iso, # DB에는 변환된 한국 시간이 저장됨
                "duration_minutes": duration,
                "status": "pending",
                "original_timezone": selected_zone_name # 나중에 확인용으로 기록
            }
            supabase.table("webinar_reservations").insert(data).execute()
            
            st.success(f"🎉 예약 완료! {selected_zone_name} 현지 시간({local_dt.strftime('%H:%M')})은 \n"
                       f"**한국 시간으로 {scheduled_kst.strftime('%Y-%m-%d %H:%M')}**입니다.")
            st.balloons()

    # 기존 예약 리스트 보여주기 (예전 성공 화면 구성)
    st.markdown("---")
    st.subheader("📝 현재 예약 대기 목록")
    res = supabase.table("webinar_reservations").select("*").eq("status", "pending").order("scheduled_at").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        # 시간 가독성 좋게 변경
        df['scheduled_at'] = pd.to_datetime(df['scheduled_at']).dt.strftime('%m/%d %H:%M')
        st.table(df[['title', 'scheduled_at', 'duration_minutes']])
    else:
        st.write("대기 중인 예약이 없습니다.")

# --- 5. [화면 2] 녹화 내역 확인 ---
elif menu == "📂 녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    # (파일 목록 로직은 이전과 동일하게 유지)
    blobs = list(bucket.list_blobs(prefix="recordings/"))
    if not blobs:
        st.info("저장된 영상이 없습니다.")
    else:
        for blob in blobs:
            if blob.name.endswith((".webm", ".mp4")):
                col1, col2 = st.columns([3, 1])
                with col1: st.write(f"📄 {blob.name.split('/')[-1]}")
                with col2:
                    url = blob.generate_signed_url(expiration=timedelta(hours=1))
                    st.link_button("⬇️ 다운로드", url)

# --- 6. [화면 3] 시스템 상태 ---
elif menu == "⚙️ 시스템 상태":
    st.header("⚙️ 시스템 상태")
    st.success("✅ 구글 클라우드 및 Supabase 연결 정상")
    st.info("녹화 봇은 예약 시간 5분 전에 자동으로 Cloud Run에서 기동됩니다.")