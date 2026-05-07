# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.1 (Legacy Modern)
# DESCRIPTION: 통합 예약 시스템 & Firebase 파일 관리자
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
import datetime as dt
from datetime import datetime
from pathlib import Path
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

# --- 1. 페이지 설정 및 타임존 ---
st.set_page_config(page_title="Plant TI Webinar Center", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207"

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore"
}

# --- 2. 초기화 (Firebase & Supabase) ---
try:
    get_app()
except ValueError:
    cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT") or os.getenv("FIREBASE_SERVICE_ACCOUNT")
    cred_info = json.loads(cred_json)
    bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME") or os.getenv("FIREBASE_BUCKET_NAME")
    initialize_app(credentials.Certificate(cred_info), {'storageBucket': bucket_name})

supabase = create_client(
    st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL"),
    st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
)
bucket = storage.bucket()

# --- 3. UI 테마 및 스타일 (v1.6.0 대우건설 스타일) ---
st.sidebar.markdown("### 🏗️ Daewoo E&C")
st.sidebar.markdown(f'#### Plant TI Team <span style="font-size:12px; color:gray;">v2.3.1</span>', unsafe_allow_html=True)
dark_mode = st.sidebar.toggle("🌙 다크 모드", value=True)

if dark_mode:
    bg, txt, pt, box = "#0e1117", "#FFFFFF", "#4dabff", "#2d3748"
else:
    bg, txt, pt, box = "#FFFFFF", "#1A1A1A", "#000080", "#F0F7FF"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .time-box {{ background-color: {box}; padding: 20px; border-radius: 12px; border: 2px solid {pt}; margin: 15px 0; }}
    .kst-highlight {{ color: #FF5733; font-weight: 900; font-size: 22px; }}
    .file-card {{ background-color: {box}; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid {pt}; }}
    </style>
""", unsafe_allow_html=True)

# --- [AI 주소 분석 함수] ---
def analyze_url_feasibility(url):
    if not url: return None, None
    url = url.lower()
    if any(x in url for x in ["zoom.us", "teams.microsoft", "webex.com"]):
        return "🔴 녹화 불가", "전용 앱 실행이 필요한 플랫폼은 시스템상 접근이 차단됩니다."
    elif any(x in url for x in ["gasworld", "linkedin", "on24"]):
        return "🟠 주의 (보안 장벽)", "로그인이 필수인 사이트입니다. 봇이 입력을 시도하지만 실패 확률이 있습니다."
    elif any(x in url for x in ["youtube", "vimeo"]):
        return "🟢 녹화 가능 (높음)", "공개 플랫폼입니다. 원활한 녹화가 예상됩니다."
    return "🟡 확인 필요", "일반 웹페이지입니다. 보안 설정에 따라 결과가 달라질 수 있습니다."

# --- 4. 사이드바 메뉴 ---
with st.sidebar.expander("🔐 관리자 모드"):
    admin_input = st.text_input("Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

menu = st.sidebar.radio("Menu", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 5. [Menu 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.markdown('# 📅 웨비나 예약 및 시스템 현황')
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        title = st.text_input("1. 웨비나 명칭")
        url_input = st.text_input("2. 접속 URL")
        
        status_tag, advice = analyze_url_feasibility(url_input)
        if status_tag:
            st.info(f"**AI 분석: {status_tag}** \n\n {advice}")
        
        c1, c2 = st.columns(2)
        with c1: user_email = st.text_input("3. 로그인 이메일", value=os.getenv("USER_EMAIL", ""))
        with c2: duration = st.number_input("4. 녹화 시간(분)", min_value=1, value=60)
            
        c3, c4 = st.columns(2)
        with c3: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c4: rec_date = st.date_input("6. 시작 날짜")
        
        rec_time = st.time_input("7. 시작 시각")
        
        # 시각 변환
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        rec_dt = target_tz.localize(datetime.combine(rec_date, rec_time))
        k_dt = rec_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-box">
                <span style="color:gray;">🚀 실제 녹화 시작 시각 (KST):</span><br>
                <span class="kst-highlight">{k_dt.strftime("%Y-%m-%d %H:%M")}</span>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 예약 확정", use_container_width=True):
            if title and url_input:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input, "email": user_email,
                    "scheduled_at": rec_dt.isoformat(), "duration_min": duration,
                    "status": "pending"
                }).execute()
                st.success("예약이 등록되었습니다.")
                st.rerun()

    st.markdown("---")
    st.subheader("📊 현재 예약 리스트")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "trigger", "running"]).order("scheduled_at").execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 {item['webinar_url']}")
                if st.button("🗑️ 예약 취소", key=f"can_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 6. [Menu 2] 녹화 완료 파일 (v1.6.0 디자인 + Firebase 보안) ---
elif menu == "🎥 녹화 완료 파일":
    st.markdown('# 🎥 녹화 결과 관리')
    
    # 상단 요약 정보
    blobs = list(bucket.list_blobs(prefix="webinars/"))
    total_size = sum([b.size for b in blobs]) / (1024*1024)
    
    c1, c2 = st.columns(2)
    c1.metric("보관 중인 파일", f"{len(blobs)} 개")
    c2.metric("전체 사용 용량", f"{total_size:.2f} MB / 5120 MB")

    st.divider()

    if not blobs:
        st.info("완료된 녹화 파일이 없습니다.")
    else:
        # 최신순 정렬
        blobs.sort(key=lambda x: x.updated, reverse=True)
        
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            f_date = blob.updated.strftime('%Y-%m-%d %H:%M')
            f_size = f"{blob.size / (1024*1024):.2f} MB"
            
            with st.container():
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.markdown(f"""
                    <div class="file-card">
                        <b>📺 {f_name}</b><br>
                        <span style="font-size:12px; color:gray;">📅 {f_date} | 💾 {f_size}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Firebase 보안 링크 생성
                    url = blob.generate_signed_url(expiration=dt.timedelta(minutes=30))
                    st.link_button("📥 다운로드", url, use_container_width=True)
                
                with col3:
                    if is_admin:
                        if st.button("🗑️ 삭제", key=f"del_{blob.name}", use_container_width=True):
                            blob.delete()
                            supabase.table("webinar_reservations").update({"video_url": None}).eq("video_url", blob.name).execute()
                            st.rerun()
                    else:
                        st.button("🔒", disabled=True, use_container_width=True)

st.sidebar.divider()
st.sidebar.caption("Daewoo E&C Plant TI Team")
