import streamlit as st
import os
import json
import datetime as dt
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

# 1. 페이지 기본 설정 (v1.6.0 스타일의 와이드 모드)
st.set_page_config(page_title="Plant TI Webinar Admin", page_icon="🎬", layout="wide")

# CSS를 통한 v1.6.0 디자인 커스텀
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .file-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #003399; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .stButton>button { width: 100%; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

load_dotenv()

# --- [초기화 로직] ---
try:
    get_app()
except ValueError:
    cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_info = json.loads(cred_json)
    bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")
    initialize_app(credentials.Certificate(cred_info), {'storageBucket': bucket_name})

supabase_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)
bucket = storage.bucket()

# --- [상단 대시보드 - v1.6.0 상징] ---
st.title("🎬 Plant TI Webinar Control Center")
st.caption("v1.6.0 Legacy Design Mode")

blobs = list(bucket.list_blobs(prefix="webinars/"))
total_count = len(blobs)
total_size_mb = sum([b.size for b in blobs]) / (1024 * 1024)

# KPI 지표 배치
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("총 녹화 본", f"{total_count} 개")
with m2:
    st.metric("총 사용 용량", f"{total_size_mb:.2f} MB")
with m3:
    # 5GB 기준 사용률
    storage_pct = (total_size_mb / 5120) * 100
    st.metric("창고 점유율", f"{storage_pct:.1f} %")

st.divider()

# --- [메인 리스트 구역] ---
if not blobs:
    st.info("현재 금고에 저장된 녹화 파일이 없습니다.")
else:
    # 최신순 정렬
    blobs.sort(key=lambda x: x.updated, reverse=True)
    
    st.subheader("📁 녹화 파일 리스트")
    
    for blob in blobs:
        file_name = blob.name.replace("webinars/", "")
        file_date = blob.updated.strftime('%Y-%m-%d %H:%M:%S')
        file_size = f"{blob.size / (1024*1024):.2f} MB"
        
        # 카드 디자인 시작
        with st.container():
            # v1.6.0 스타일의 깔끔한 카드 레이아웃
            col1, col2, col3 = st.columns([4, 1, 1])
            
            with col1:
                st.markdown(f"""
                <div style="padding-left: 10px;">
                    <b style="font-size: 18px; color: #1f1f1f;">{file_name}</b><br>
                    <span style="color: #666; font-size: 14px;">📅 녹화일시: {file_date} | 💾 용량: {file_size}</span>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # 다운로드 링크 생성
                download_url = blob.generate_signed_url(expiration=dt.timedelta(minutes=30))
                st.link_button("📥 다운로드", download_url, use_container_width=True)
            
            with col3:
                # 삭제 버튼 (v1.6.0의 직관적인 배치)
                if st.button("🗑️ 삭제", key=f"del_{blob.name}", type="secondary", use_container_width=True):
                    blob.delete()
                    # Supabase 업데이트 (영상 정보 초기화)
                    supabase.table("webinar_reservations").update({"video_url": None}).eq("video_url", blob.name).execute()
                    st.toast(f"{file_name} 삭제 완료!")
                    st.rerun()
            
            st.markdown("<hr style='margin: 10px 0; border: 0.5px solid #eee;'>", unsafe_allow_html=True)

st.sidebar.header("System Status")
st.sidebar.success("Cloud Connection: Active")
st.sidebar.info(f"Last Sync: {dt.datetime.now().strftime('%H:%M:%S')}")
if st.sidebar.button("🔄 리스트 새로고침"):
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("DAEWOO E&C Plant TI Team")
