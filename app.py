import streamlit as st
import json
import os
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client

# --- 1. 페이지 기본 설정 ---
st.set_page_config(page_title="Plant TI Webinar Recorder", page_icon="🎥", layout="wide")

# --- 2. 보안 인증 및 클라이언트 설정 (핵심!) ---
@st.cache_resource
def init_connection():
    # A. 구글 클라우드(Firebase Storage) 인증
    if "FIREBASE_KEY" in st.secrets:
        # 웹 배포 환경: Secrets에서 읽기
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
    else:
        # 로컬 개발 환경: 파일에서 읽기
        creds = service_account.Credentials.from_service_account_file('firebase_key.json')
    
    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    
    # B. Supabase 연결 (Secrets 사용)
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase_client = create_client(url, key)
    
    return storage_client, supabase_client

try:
    storage_client, supabase = init_connection()
    # 버킷 이름은 사용자님의 Firebase 설정에 맞게 수정하세요.
    bucket_name = "webinar-recorder.firebasestorage.app" 
    bucket = storage_client.bucket(bucket_name)
except Exception as e:
    st.error(f"연결 실패: {e}")
    st.stop()

# --- 3. UI 구성 (사이드바) ---
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면", ["새 녹화 예약", "녹화 내역 확인", "시스템 상태"])

# --- 4. 메인 화면: 새 녹화 예약 ---
if menu == "새 녹화 예약":
    st.header("🎥 새 녹화 작업 예약")
    
    with st.form("recording_form"):
        webinar_url = st.text_input("웨비나 URL (예: Zoom, YouTube, Teams 등)")
        title = st.text_input("세미나 제목")
        
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("예약 날짜", datetime.now())
        with col2:
            time = st.time_input("시작 시간 (실제 시간 5분 전 추천)", datetime.now())
            
        duration = st.number_input("녹화 지속 시간 (분 단위)", min_value=10, max_value=300, value=60)
        
        submit = st.form_submit_button("예약 확정")
        
        if submit:
            scheduled_at = datetime.combine(date, time).isoformat()
            
            # Supabase DB에 예약 정보 저장
            data = {
                "url": webinar_url,
                "title": title,
                "scheduled_at": scheduled_at,
                "duration_minutes": duration,
                "status": "pending"
            }
            response = supabase.table("webinar_reservations").insert(data).execute()
            
            if response:
                st.success(f"✅ '{title}' 예약이 완료되었습니다. (예정 시각: {scheduled_at})")
                st.balloons()

# --- 5. 메인 화면: 녹화 내역 확인 ---
elif menu == "녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    
    # Firebase Storage에서 파일 목록 가져오기
    try:
        blobs = list(bucket.list_blobs(prefix="recordings/"))
        if not blobs:
            st.info("아직 저장된 영상이 없습니다.")
        else:
            for blob in blobs:
                if blob.name.endswith(".webm") or blob.name.endswith(".mp4"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📄 {blob.name.replace('recordings/', '')}")
                    with col2:
                        # 1시간 동안 유효한 다운로드 링크 생성
                        url = blob.generate_signed_url(expiration=timedelta(hours=1))
                        st.markdown(f"[⬇️ 다운로드]({url})")
    except Exception as e:
        st.error(f"파일 목록을 불러올 수 없습니다: {e}")

# --- 6. 시스템 상태 (모니터링) ---
elif menu == "시스템 상태":
    st.header("⚙️ 시스템 상태 모니터링")
    st.info("녹화 엔진(Cloud Run)은 Supabase 알람(pg_cron)에 의해 10분마다 자동으로 깨어납니다.")
    
    # 최근 예약 현황 요약
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(5).execute()
    if res.data:
        st.subheader("최근 예약 상태 (Top 5)")
        st.table(pd.DataFrame(res.data)[['title', 'scheduled_at', 'status']])