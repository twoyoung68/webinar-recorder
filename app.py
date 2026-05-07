import streamlit as st
import os
import json
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

# 페이지 설정
st.set_page_config(page_title="Plant TI Webinar Admin", page_icon="🎬")
load_dotenv()

# --- [Firebase/Supabase 초기화] ---
try:
    get_app()
except ValueError:
    # Streamlit Secrets 또는 .env에서 가져오기
    cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_info = json.loads(cred_json)
    bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")
    initialize_app(credentials.Certificate(cred_info), {'storageBucket': bucket_name})

supabase_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
supabase_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)
bucket = storage.bucket()

st.title("🎬 Plant TI 웨비나 금고")
st.info("파이어베이스에 저장된 녹화 파일을 관리합니다.")

# --- [파일 목록 불러오기] ---
blobs = list(bucket.list_blobs(prefix="webinars/"))

if not blobs:
    st.warning("저장된 영상이 없습니다.")
else:
    for blob in blobs:
        col1, col2, col3 = st.columns([3, 1, 1])
        file_name = blob.name.replace("webinars/", "")
        
        with col1:
            st.write(f"📄 {file_name}")
            st.caption(f"용량: {round(blob.size / (1024*1024), 2)}MB | 날짜: {blob.updated.strftime('%Y-%m-%d %H:%M')}")
        
        with col2:
            # 다운로드 링크 생성 (10분 유효)
            url = blob.generate_signed_url(expiration=600)
            st.link_button("⬇️ 다운로드", url)
            
        with col3:
            if st.button("❌ 삭제", key=blob.name):
                blob.delete()
                # Supabase DB 업데이트
                supabase.table("webinar_reservations").update({"video_url": None}).eq("video_url", blob.name).execute()
                st.success("삭제되었습니다!")
                st.rerun()

st.divider()
st.caption("대우건설 Plant TI Team - Webinar Auto-System v2.3.0")
