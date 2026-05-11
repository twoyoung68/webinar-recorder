# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.2 (Stable Update)
# DESCRIPTION: Firebase 초기화 에러 해결 및 통합 관리자
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

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="Plant TI Center", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207"

# --- 2. [핵심 수정] Firebase & Supabase 초기화 엔진 ---
def init_connections():
    # Firebase 초기화
    try:
        firebase_admin.get_app()
    except ValueError:
        # 1. Secrets에서 값 가져오기 (가장 안전한 방식)
        cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
        bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")

        if not cred_json:
            st.error("❌ Secrets에 'FIREBASE_SERVICE_ACCOUNT'가 설정되지 않았습니다.")
            st.stop()
        
        try:
            # JSON 문자열을 딕셔너리로 변환 (strict=False로 줄바꿈 등 유연하게 처리)
            cred_info = json.loads(cred_json, strict=False)
            # 버킷 이름에서 gs:// 가 있으면 제거
            clean_bucket_name = bucket_name.replace("gs://", "") if bucket_name else ""
            
            initialize_app(credentials.Certificate(cred_info), {
                'storageBucket': clean_bucket_name
            })
        except Exception as e:
            st.error(f"❌ Firebase 초기화 실패: {e}")
            st.info("💡 Secrets에 JSON 키를 넣을 때 따옴표 3개(''' ''')로 감쌌는지 확인하세요.")
            st.stop()

    # Supabase 연결
    s_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

# --- 3. UI 테마 설정 (v1.6.0 스타일 유지) ---
st.sidebar.markdown("### 🏗️ Daewoo E&C\n#### Plant TI Team")
dark_mode = st.sidebar.toggle("🌙 다크 모드", value=True)

if dark_mode:
    bg, txt, pt, box = "#0e1117", "#FFFFFF", "#4dabff", "#2d3748"
else:
    bg, txt, pt, box = "#FFFFFF", "#1A1A1A", "#000080", "#F0F7FF"

st.markdown(f"<style>.stApp {{ background-color: {bg}; color: {txt}; }} .time-box {{ background-color: {box}; padding: 20px; border-radius: 12px; border: 2px solid {pt}; margin: 15px 0; }} .kst-highlight {{ color: #FF5733; font-weight: 900; font-size: 22px; }}</style>", unsafe_allow_html=True)

# --- 4. 사이드바 메뉴 ---
menu = st.sidebar.radio("Menu", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])
admin_pw = st.sidebar.text_input("Admin Password", type="password")
is_admin = (admin_pw == MASTER_PASSWORD)

# --- 5. [Menu 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 및 시스템 현황")
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        title = st.text_input("1. 웨비나 명칭")
        url_input = st.text_input("2. 접속 URL")
        
        c1, c2 = st.columns(2)
        with c1: user_email = st.text_input("3. 로그인 이메일", value=os.getenv("USER_EMAIL", ""))
        with c2: duration = st.number_input("4. 녹화 시간(분)", min_value=1, value=60)
            
        c3, c4 = st.columns(2)
        with c3: rec_date = st.date_input("5. 시작 날짜")
        with c4: rec_time = st.time_input("6. 시작 시각")

        # 시간 변환
        rec_dt = KST.localize(datetime.combine(rec_date, rec_time))
        
        st.markdown(f"""<div class="time-box"><span style="color:gray;">🚀 실제 녹화 시작 시각 (KST):</span><br><span class="kst-highlight">{rec_dt.strftime("%Y-%m-%d %H:%M")}</span></div>""", unsafe_allow_html=True)

        if st.button("🚀 예약 확정", use_container_width=True):
            if title and url_input:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input, "email": user_email,
                    "scheduled_at": rec_dt.isoformat(), "duration_min": duration, "status": "pending"
                }).execute()
                st.success("예약이 등록되었습니다.")
                st.rerun()

    st.divider()
    st.subheader("📊 대기 중인 일정")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 {item['webinar_url']}")
                if st.button("🗑️ 예약 취소", key=f"can_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 6. [Menu 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과 관리")
    blobs = list(bucket.list_blobs(prefix="webinars/"))
    
    if not blobs:
        st.info("보관 중인 영상이 없습니다.")
    else:
        blobs.sort(key=lambda x: x.updated, reverse=True)
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            with st.container(border=True):
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"**📺 {f_name}**")
                    st.caption(f"📅 {blob.updated.strftime('%Y-%m-%d %H:%M')} | 💾 {blob.size/(1024*1024):.1f} MB")
                with col2:
                    url = blob.generate_signed_url(expiration=dt.timedelta(minutes=30))
                    st.link_button("📥 다운로드", url, use_container_width=True)
                with col3:
                    if is_admin:
                        if st.button("🗑️ 삭제", key=f"del_{blob.name}", use_container_width=True):
                            blob.delete()
                            supabase.table("webinar_reservations").update({"video_url": None}).eq("video_url", blob.name).execute()
                            st.rerun()
