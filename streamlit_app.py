# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.5.0 (Safety First Edition)
# DESCRIPTION: 근무 중(로컬) vs 야간(클라우드) 선택 시스템
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
from datetime import datetime
import firebase_admin
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

st.set_page_config(page_title="Plant TI Center v2.5.0", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')

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

# UI 스타일
st.sidebar.markdown(f"""<div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;"><h2 style="margin:0;">🏗️ DAEWOO E&C</h2><p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.5.0</p></div>""", unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

if menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 시스템 (v2.5.0)")
    
    with st.container(border=True):
        st.subheader("📝 신규 일정 등록")
        title = st.text_input("1. 웨비나 명칭")
        url_input = st.text_input("2. 접속 URL")
        
        # [모드 선택 스위치]
        rec_mode = st.radio("3. 녹화 모드 선택", 
                            ["☁️ 클라우드 자동 (야간/퇴근용)", "🖥️ 로컬 하이브리드 (근무 중/수동용)"],
                            captions=["노트북을 끄고 퇴근할 때 사용 (봇 감지 시 실패 가능)", "노트북에서 화면을 직접 열어둘 때 사용 (가장 안전)"])
        
        mode_val = 'cloud' if "클라우드" in rec_mode else 'local'
        
        c1, c2 = st.columns(2)
        with c1: duration = st.number_input("4. 녹화 시간(분)", min_value=1, value=60)
        with c2: rec_date = st.date_input("5. 시작 날짜")
        rec_time = st.time_input("6. 시작 시각")

        if st.button("🚀 예약 확정", use_container_width=True):
            if title and url_input:
                kst_dt = KST.localize(datetime.combine(rec_date, rec_time))
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input, "scheduled_at": kst_dt.isoformat(),
                    "duration_min": duration, "status": "pending", "rec_mode": mode_val
                }).execute()
                st.success(f"✅ {rec_mode} 모드로 예약되었습니다.")
                st.rerun()

    st.divider()
    st.subheader("📊 예약 현황")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    for item in res.data:
        mode_icon = "🖥️" if item.get('rec_mode') == 'local' else "☁️"
        with st.expander(f"{mode_icon} {item['title']} | {item['duration_min']}분"):
            st.write(f"🔗 {item['webinar_url']}")
            if st.button("🗑️ 취소", key=f"can_{item['id']}"):
                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                st.rerun()

elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 결과 관리")
    # ... (기존 파일 리스트 및 다운로드 로직 유지) ...
