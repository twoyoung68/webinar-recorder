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
    
    # [인증 우선순위 1] Streamlit Secrets (웹 배포용)
    if "FIREBASE_KEY" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
        except Exception as e:
            st.error(f"Secrets 인증 로드 실패: {e}")
            
    # [인증 우선순위 2] 로컬 파일 (내 컴퓨터 테스트용 - .gitignore에 등록됨)
    elif os.path.exists('firebase_key.json'):
        try:
            creds = service_account.Credentials.from_service_account_file('firebase_key.json')
        except Exception as e:
            st.error(f"로컬 파일 인증 로드 실패: {e}")

    # 최종 체크: 인증 정보가 없으면 중단
    if creds is None:
        st.error("보안 키(Secrets 또는 JSON 파일)가 없습니다. 설정을 확인해 주세요.")
        st.stop()
        
    # 구글 클라우드 스토리지 클라이언트
    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    
    # Supabase 클라이언트 (Secrets 필수)
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(supabase_url, supabase_key)
    
    return storage_client, supabase_client

# 전역 클라이언트 초기화
storage_client, supabase = init_all_connections()
bucket_name = "webinar-recorder-plant-titeam.appspot.com"
bucket = storage_client.bucket(bucket_name)

# --- 3. 사이드바 (정보창 및 메뉴) ---
with st.sidebar:
    st.title("🎥 Webinar Recorder")
    st.info(f"**현재 한국 시간(KST):**\n{datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    
    st.markdown("---")
    menu = st.radio("메뉴 이동", ["📅 웨비나 녹화 예약", "📂 녹화 내역 확인", "⚙️ 시스템 상태"])
    
    st.markdown("---")
    st.subheader("📊 시스템 정보")
    st.write(f"**Target:** Plant TI DX Project")
    st.write(f"**Storage:** Firebase Storage")
    st.caption("Developed by Plant TI Team")

# --- 4. [화면 1] 웨비나 녹화 예약 ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 예약")
    
    with st.form("recording_form"):
        title = st.text_input("세미나 제목", placeholder="예: 2026 SMR 기술 전략 세미나")
        webinar_url = st.text_input("웨비나 URL", placeholder="https://zoom.us/j/...")
        
        st.markdown("#### 🌍 시간대 설정")
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
            # 입력받은 시간을 현지 시간대로 결합 후 KST로 변환
            local_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
            scheduled_kst = local_dt.astimezone(KST)
            scheduled_iso = scheduled_kst.isoformat()
            
            data = {
                "title": title,
                "url": webinar_url,
                "scheduled_at": scheduled_iso,
                "duration_minutes": duration,
                "status": "pending"
            }
            try:
                supabase.table("webinar_reservations").insert(data).execute()
                st.success(f"🎉 '{title}' 예약 완료! 한국 시각 {scheduled_kst.strftime('%Y-%m-%d %H:%M')}에 시작됩니다.")
                st.balloons()
            except Exception as e:
                st.error(f"예약 저장 실패: {e}")

    # 현재 예약 대기 목록 출력 (방어적 코딩 적용)
    st.markdown("---")
    st.subheader("📝 현재 예약 대기 목록")
    try:
        res = supabase.table("webinar_reservations").select("*").eq("status", "pending").order("scheduled_at").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            # 화면에 표시할 컬럼만 안전하게 필터링
            display_cols = ['title', 'scheduled_at', 'duration_minutes']
            existing_cols = [c for c in display_cols if c in df.columns]
            
            if 'scheduled_at' in df.columns:
                df['scheduled_at'] = pd.to_datetime(df['scheduled_at']).dt.strftime('%m/%d %H:%M')
            
            if existing_cols:
                st.table(df[existing_cols])
        else:
            st.write("대기 중인 예약이 없습니다.")
    except Exception as e:
        st.error(f"목록 불러오기 실패: {e}")

# --- 5. [화면 2] 녹화 내역 확인 ---
elif menu == "📂 녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    try:
        blobs = list(bucket.list_blobs(prefix="recordings/"))
        if not blobs:
            st.info("저장된 영상이 없습니다.")
        else:
            for blob in blobs:
                if blob.name.endswith((".webm", ".mp4")):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📄 {blob.name.split('/')[-1]}")
                    with col2:
                        url = blob.generate_signed_url(expiration=timedelta(hours=1))
                        st.link_button("⬇️ 다운로드", url)
    except Exception as e:
        st.error(f"파일 목록 불러오기 실패: {e}")

# --- 6. [화면 3] 시스템 상태 ---
elif menu == "⚙️ 시스템 상태":
    st.header("⚙️ 시스템 상태")
    st.success("✅ 구글 클라우드 및 Supabase 연결 정상")
    st.info("녹화 봇은 예약 시간 5분 전에 자동으로 Cloud Run에서 기동됩니다.")