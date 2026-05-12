# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.5.4 (Control Center Edition)
# DESCRIPTION: v2.3.7 기반 UI + 구글 캘린더 안내 및 상세 현황
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

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Control Center v2.5.4", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')

# --- 2. 서비스 연결 초기화 ---
@st.cache_resource
def init_connections():
    try:
        get_app()
    except ValueError:
        cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT")
        bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME")
        initialize_app(credentials.Certificate(json.loads(cred_json, strict=False)), {
            'storageBucket': bucket_name.replace("gs://", "")
        })
    s_url = st.secrets.get("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

# --- 3. UI 디자인 및 사이드바 ---
st.sidebar.markdown(f"""
    <div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;">
        <h2 style="margin:0;">🏗️ DAEWOO E&C</h2>
        <p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.5.4</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 (통합 컨트롤러) ---
if menu == "📅 예약 및 현황":
    st.title("📅 웨비나 자동화 관제 센터")
    
    # [안내 섹션] 구글 캘린더 예약 가이드
    with st.container(border=True):
        col_txt, col_btn = st.columns([3, 1])
        with col_txt:
            st.markdown("""
            ### 🚀 웨비나 예약 방법 (10분 전 자동 감지)
            이 시스템은 **구글 캘린더**와 연동되어 작동합니다.
            1. 아래 버튼을 눌러 **구글 캘린더**를 여세요.
            2. **제목**: 웨비나 명칭 입력 (예: 가스 월드 수전해 세미나)
            3. **설명/장소**: `https://...` 주소를 반드시 포함하세요.
            4. **자동화**: 10분마다 시스템이 감지하여 깃허브에서 녹화를 시작합니다.
            """)
        with col_btn:
            st.write(" ") 
            st.write(" ")
            st.link_button("📅 내 구글 캘린더 열기", "https://calendar.google.com/", use_container_width=True, type="primary")

    st.divider()
    
    # [현황 섹션] 상세 시간 정보 표시
    st.subheader("📊 현재 예약 및 녹화 현황")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    
    if not res.data:
        st.info("현재 대기 중인 예약 일정이 없습니다. 구글 캘린더에 일정을 등록해 보세요.")
    else:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
            created = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            with st.expander(f"[{item['status'].upper()}] {item['title']} | ⏰ {s_kst} 시작"):
                st.markdown(f"""
                - **📝 예약 등록 시각:** `{created}`
                - **⏰ 녹화 시작 예정:** `{s_kst}`
                - **🕒 녹화 지속 시간:** `{item.get('duration_min', 60)}분`
                - **🔗 접속 URL:** {item['webinar_url']}
                """)
                if st.button("🗑️ 일정 취소", key=f"can_{item['id']}", use_container_width=True):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과물 관리")
    res_db = supabase.table("webinar_reservations").select("*").execute()
    db_map = {item['video_url']: item for item in res_db.data if item.get('video_url')}
    blobs = list(bucket.list_blobs(prefix="webinars/"))
    blobs.sort(key=lambda x: x.updated, reverse=True)

    if not blobs:
        st.info("보관 중인 영상이 없습니다.")
    else:
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            db_item = db_map.get(blob.name, {})
            dl_count = db_item.get('download_count', 0)
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.write(f"**📺 {f_name}**")
                    st.caption(f"📅 완료: {blob.updated.strftime('%Y-%m-%d %H:%M')} | 📥 다운로드: {dl_count}회")
                with c2:
                    url = blob.generate_signed_url(expiration=dt.timedelta(minutes=60), response_disposition=f"attachment; filename={f_name}")
                    if st.link_button("📥 저장", url, use_container_width=True):
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").update({"download_count": dl_count + 1}).eq("id", db_item['id']).execute()
                with c3:
                    if st.button("🗑️ 삭제", key=f"del_{blob.name}", use_container_width=True):
                        blob.delete()
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").delete().eq("id", db_item['id']).execute()
                        st.rerun()
