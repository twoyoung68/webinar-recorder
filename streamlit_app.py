# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.4.2 (Cookie Vault Edition)
# DESCRIPTION: 도메인별 쿠키 관리 및 지능형 매칭 시스템
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
import datetime as dt
from datetime import datetime
from urllib.parse import urlparse
import firebase_admin
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

st.set_page_config(page_title="Plant TI Center v2.4.2", page_icon="🎥", layout="wide")
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
            'storage_Bucket': bucket_name.replace("gs://", "")
        })
    s_url = st.secrets.get("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

st.sidebar.markdown(f"""<div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;"><h2 style="margin:0;">🏗️ DAEWOO E&C</h2><p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.4.2</p></div>""", unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일", "🔐 쿠키 금고"])

# --- [메뉴 3] 쿠키 금고 (신설) ---
if menu == "🔐 쿠키 금고":
    st.title("🔐 쿠키 금고 (Cookie Vault)")
    st.info("회사별/사이트별 로그인 쿠키를 관리합니다. 여기에 저장된 쿠키는 녹화 시 자동 적용됩니다.")

    with st.container(border=True):
        st.subheader("🍪 새 쿠키 등록")
        domain_input = st.text_input("1. 사이트 도메인 (예: youtube.com, gasworld.com)")
        cookie_json = st.text_area("2. 쿠키 JSON 데이터 (EditThisCookie에서 Export한 값)")
        
        if st.button("💾 금고에 저장", use_container_width=True):
            if domain_input and cookie_json:
                try:
                    c_data = json.loads(cookie_json)
                    supabase.table("webinar_cookies").upsert({
                        "domain": domain_input.lower(),
                        "cookie_data": c_data,
                        "updated_at": datetime.now().isoformat()
                    }).execute()
                    st.success(f"✅ {domain_input}의 쿠키가 안전하게 저장되었습니다.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 올바른 JSON 형식이 아닙니다: {e}")

    st.divider()
    st.subheader("📋 저장된 쿠키 목록")
    res_c = supabase.table("webinar_cookies").select("*").execute()
    if res_c.data:
        for c in res_c.data:
            with st.expander(f"🔑 {c['domain']} (업데이트: {c['updated_at'][:10]})"):
                st.json(c['cookie_data'][:2]) # 보안상 앞부분만 살짝 표시
                if st.button(f"🗑️ {c['domain']} 쿠키 삭제", key=f"del_c_{c['id']}"):
                    supabase.table("webinar_cookies").delete().eq("id", c['id']).execute()
                    st.rerun()

# --- [메뉴 1] 예약 로직 ---
elif menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 및 현황")
    # (v2.3.8의 예약 로직 그대로 유지)
    # ... 예약 입력 폼 및 리스트 출력 ...
    # (사용자께서 이미 잘 사용 중이신 v2.3.8의 코드가 여기에 들어갑니다)

# --- [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과 리스트")
    # (v2.3.8의 파일 관리 로직 그대로 유지)
    # ... 파일 리스트 및 노트북 저장 버튼 ...
