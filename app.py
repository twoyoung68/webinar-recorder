import streamlit as st
import os, pandas as pd, requests, pytz
from supabase import create_client
from datetime import datetime

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207"

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul", "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles", "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris", "싱가포르/대만 (CST)": "Asia/Singapore", "일본 (JST)": "Asia/Tokyo"
}

# --- 2. 디자인 및 가독성 ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)
if dark_mode:
    bg, txt, sub = "#0e1117", "#FFFFFF", "#B0B0B0"
    pb, pt = "#1e293b", "#3b82f6"
else:
    bg, txt, sub = "#FFFFFF", "#1A1A1A", "#555555"
    pb, pt = "#F0F7FF", "#004a99"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {pt} !important; }}
    .time-preview {{ background-color: {pb}; padding: 15px; border-radius: 10px; border: 2px solid {pt}; margin: 10px 0; }}
    .error-box {{ background-color: #ffebee; color: #c62828; padding: 10px; border-radius: 5px; border-left: 5px solid #d32f2f; margin: 10px 0; font-size: 14px; font-weight: 600; }}
    .kst-val {{ color: #FF5733; font-weight: 800; }}
    </style>
""", unsafe_allow_html=True)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 ---
st.sidebar.markdown("### 🏗️ Daewoo E&C")
st.sidebar.markdown("#### Plant TI Team Webinar")
st.sidebar.markdown("---")
admin_input = st.sidebar.text_input("Master Password", type="password")
is_admin = (admin_input == MASTER_PASSWORD)
menu = st.sidebar.radio("Menu", ["📅 예약 현황", "🎥 녹화 관리"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 현황":
    st.title("📅 웨비나 예약")
    with st.container(border=True):
        title = st.text_input("1. 웨비나 명칭")
        url = st.text_input("2. 접속 URL")
        c1, c2 = st.columns(2)
        with c1: email = st.text_input("3. 확인용 이메일")
        with c2: pw = st.text_input("4. 삭제 비번", type="password")
        
        c3, c4 = st.columns(2)
        with c3: zone = st.selectbox("5. 타임존", list(WORLD_ZONES.keys()))
        with c4: dur = st.number_input("6. 녹화 시간(분)", value=60)
        
        t_tz = pytz.timezone(WORLD_ZONES[zone])
        col_d, col_t = st.columns(2)
        with col_d: d_in = st.date_input("7. 현지 날짜")
        with col_t: t_in = st.time_input("8. 현지 시각")
        
        l_dt = t_tz.localize(datetime.combine(d_in, t_in))
        k_dt = l_dt.astimezone(KST)
        
        st.markdown(f'<div class="time-preview">🚀 한국 시작 시각: <span class="kst-val">{k_dt.strftime("%Y-%m-%d %H:%M")} (KST)</span></div>', unsafe_allow_html=True)
        
        st.markdown("---")
        chk = st.checkbox("✅ 모든 정보가 정확함을 확인했습니다.")
        if st.button("🚀 예약 확정", use_container_width=True):
            if chk and title and url:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url, "email": email, "scheduled_at": l_dt.isoformat(),
                    "duration_min": dur, "status": "pending", "timezone_name": zone, "delete_password": pw
                }).execute()
                st.success("예약 완료!")
                st.rerun()

    # 목록 표시
    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    for item in res.data:
        s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
        c_kst = pd.to_datetime(item['created_at']).astimezone(KST)
        with st.expander(f"[{item['status'].upper()}] {item['title']} | KST: {s_kst.strftime('%m-%d %H:%M')}"):
            st.write(f"🔗 URL: {item['webinar_url']}")
            st.markdown(f"🚀 시작(KST): <span class='kst-val'>{s_kst.strftime('%Y-%m-%d %H:%M')}</span>", unsafe_allow_html=True)
            st.write(f"📝 신청(KST): {c_kst.strftime('%Y-%m-%d %H:%M')}")
            if item.get('failure_reason'):
                st.markdown(f'<div class="error-box">🚨 원인: {item["failure_reason"]}</div>', unsafe_allow_html=True)
            if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                st.rerun()

# --- 5. [메뉴 2] 녹화 관리 (생략) ---
elif menu == "🎥 녹화 관리":
    st.title("🎥 녹화 결과")
    # ... (생략: 기존의 st.download_button 로직과 동일) ...