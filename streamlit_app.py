# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.3 (Smart Download Edition)
# DESCRIPTION: 강제 저장 기능 및 다운로드 상태 표시 추가
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
import datetime as dt
from datetime import datetime
import firebase_admin
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(page_title="Plant TI Center", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207"

@st.cache_resource
def init_connections():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
        bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")
        if cred_json:
            cred_info = json.loads(cred_json, strict=False)
            initialize_app(credentials.Certificate(cred_info), {'storageBucket': bucket_name.replace("gs://", "")})
    
    s_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

# --- 2. 메뉴 및 관리자 설정 ---
menu = st.sidebar.radio("Menu", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])
admin_pw = st.sidebar.text_input("Admin Password", type="password")
is_admin = (admin_pw == MASTER_PASSWORD)

# --- 3. [핵심 기능] 녹화 완료 파일 관리 ---
if menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과 관리")
    
    # Supabase에서 다운로드 상태 정보 가져오기
    res_db = supabase.table("webinar_reservations").select("id, title, video_url, status").execute()
    db_map = {item['video_url']: item for item in res_db.data if item.get('video_url')}

    blobs = list(bucket.list_blobs(prefix="webinars/"))
    
    if not blobs:
        st.info("보관 중인 영상이 없습니다.")
    else:
        blobs.sort(key=lambda x: x.updated, reverse=True)
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            db_item = db_map.get(blob.name, {})
            is_downloaded = db_item.get('status') == "downloaded"
            
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1])
                
                with col1:
                    # 다운로드 완료 시 체크 표시와 함께 강조
                    status_prefix = "✅ [다운로드됨] " if is_downloaded else "🆕 [미확인] "
                    st.write(f"**{status_prefix} {f_name}**")
                    st.caption(f"📅 {blob.updated.strftime('%Y-%m-%d %H:%M')} | 💾 {blob.size/(1024*1024):.1f} MB")
                
                with col2:
                    # [중요] 강제 다운로드(Save As)를 위한 설정
                    # Response-Content-Disposition을 사용하여 브라우저가 '파일 저장' 대화상자를 띄우게 함
                    download_url = blob.generate_signed_url(
                        expiration=dt.timedelta(minutes=30),
                        response_disposition=f"attachment; filename={f_name}"
                    )
                    
                    # 다운로드 버튼 클릭 시 상태 업데이트 로직
                    if st.link_button("📥 저장하기", download_url, use_container_width=True):
                        # 클릭 시점에 Supabase 상태를 'downloaded'로 변경
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").update({"status": "downloaded"}).eq("id", db_item['id']).execute()
                
                with col3:
                    if is_admin:
                        if st.button("🗑️ 삭제", key=f"del_{blob.name}", use_container_width=True):
                            blob.delete()
                            if db_item.get('id'):
                                supabase.table("webinar_reservations").delete().eq("id", db_item['id']).execute()
                            st.rerun()

# --- 4. 예약 및 현황 메뉴 (기존과 동일) ---
elif menu == "📅 예약 및 현황":
    st.title("📅 예약 현황")
    # ... (중략: 기존 v2.3.2의 예약 로직 유지) ...
