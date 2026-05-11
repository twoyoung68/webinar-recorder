# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.5 (Smart Tracker Edition)
# DESCRIPTION: 강제 저장, 다운로드 횟수 표시, 무암호 삭제
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

# --- 1. 페이지 및 타임존 설정 ---
st.set_page_config(page_title="Plant TI Center v2.3.5", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')

# --- 2. 초기화 (Firebase & Supabase) ---
@st.cache_resource
def init_connections():
    try:
        get_app()
    except ValueError:
        cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
        bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")
        if cred_json:
            initialize_app(credentials.Certificate(json.loads(cred_json, strict=False)), {
                'storageBucket': bucket_name.replace("gs://", "")
            })
    
    s_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

# --- 3. UI 테마 및 사이드바 버전 표시 ---
st.sidebar.markdown(f"""
    <div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;">
        <h2 style="margin:0;">🏗️ DAEWOO E&C</h2>
        <p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.3.5</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("Menu", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])
st.sidebar.divider()
st.sidebar.caption("© 2026 Daewoo E&C Plant TI Team")

# --- 4. [Menu 2] 녹화 완료 파일 관리 (Save-As & Count) ---
if menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과 관리 및 다운로드")
    st.caption("v2.3.5 업데이트: 노트북 저장 기능 및 다운로드 횟수 추적 활성화")

    # DB에서 최신 데이터(다운로드 횟수 등) 로드
    res_db = supabase.table("webinar_reservations").select("*").execute()
    db_map = {item['video_url']: item for item in res_db.data if item.get('video_url')}

    blobs = list(bucket.list_blobs(prefix="webinars/"))
    
    if not blobs:
        st.info("현재 금고에 보관 중인 영상이 없습니다.")
    else:
        blobs.sort(key=lambda x: x.updated, reverse=True)
        
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            db_item = db_map.get(blob.name, {})
            # 다운로드 횟수 가져오기 (없으면 0)
            dl_count = db_item.get('download_count', 0)
            
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1])
                
                with col1:
                    st.markdown(f"**📺 {f_name}**")
                    st.caption(f"📅 녹화: {blob.updated.strftime('%Y-%m-%d %H:%M')} | 💾 용량: {blob.size/(1024*1024):.1f} MB | 📥 다운로드: {dl_count}회")
                
                with col2:
                    # 강제 다운로드 URL 생성
                    url = blob.generate_signed_url(
                        expiration=dt.timedelta(minutes=60),
                        response_disposition=f"attachment; filename={f_name}"
                    )
                    
                    # 다운로드 버튼 및 카운트 로직
                    if st.link_button("📥 노트북 저장", url, use_container_width=True):
                        # 버튼 클릭 시 Supabase 카운트 +1
                        if db_item.get('id'):
                            new_count = dl_count + 1
                            supabase.table("webinar_reservations").update({"download_count": new_count}).eq("id", db_item['id']).execute()
                
                with col3:
                    # [수정] 비밀번호 없이 즉시 삭제
                    if st.button("🗑️ 삭제", key=f"del_{blob.name}", type="secondary", use_container_width=True):
                        blob.delete()
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").delete().eq("id", db_item['id']).execute()
                        st.rerun()

# --- 5. [Menu 1] 예약 로직 ---
elif menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 시스템")
    with st.container(border=True):
        st.subheader("📝 신규 예약")
        title = st.text_input("웨비나 명칭")
        url_input = st.text_input("접속 URL")
        
        c1, c2 = st.columns(2)
        with c1: rec_date = st.date_input("날짜")
        with c2: rec_time = st.time_input("시간")
        
        duration = st.number_input("녹화 시간(분)", min_value=1, value=60)

        if st.button("🚀 예약 확정", use_container_width=True):
            if title and url_input:
                rec_dt = KST.localize(datetime.combine(rec_date, rec_time))
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input,
                    "scheduled_at": rec_dt.isoformat(), "duration_min": duration,
                    "status": "pending", "download_count": 0
                }).execute()
                st.success("예약이 성공적으로 등록되었습니다.")
                st.rerun()

    st.divider()
    st.subheader("📊 대기 목록")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    for item in res.data:
        st.info(f"**{item['title']}** | 예정시각: {item['scheduled_at']}")
