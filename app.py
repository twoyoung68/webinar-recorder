# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.4.2 (2026-04-27)
# DESCRIPTION: Added Recording Protection Caution Notice
# ==========================================

import streamlit as st
import os
import pandas as pd
import requests
import pytz
from supabase import create_client
from datetime import datetime

# --- 1. 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207" # 지침: 내부 고정

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

# --- 2. 테마 및 스타일 ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)
if dark_mode:
    bg, txt, sub = "#0e1117", "#FFFFFF", "#B0B0B0"
    pt = "#4dabff"
    box = "#2d3748"
    caution_bg, caution_border = "#2b1b1b", "#ff4b4b"
else:
    bg, txt, sub = "#FFFFFF", "#1A1A1A", "#555555"
    pt = "#000080"
    box = "#F0F7FF"
    caution_bg, caution_border = "#fff5f5", "#ff4b4b"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {pt} !important; }}
    .time-box {{ background-color: {box}; padding: 15px; border-radius: 10px; border: 2px solid {pt}; margin: 10px 0; }}
    .kst-highlight {{ color: #FF5733; font-weight: 900; font-size: 22px; }}
    .version-text {{ font-size: 14px !important; font-weight: normal !important; color: gray !important; vertical-align: bottom; margin-left: 10px; }}
    /* 주의사항 박스 스타일 */
    .caution-container {{
        background-color: {caution_bg};
        border: 2px solid {caution_border};
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 25px;
        color: {txt};
    }}
    .caution-title {{ color: #ff4b4b; font-weight: 900; font-size: 18px; margin-bottom: 5px; }}
    </style>
""", unsafe_allow_html=True)

# 주의사항 출력 함수
def show_caution_notice():
    st.markdown(f"""
        <div class="caution-container">
            <div class="caution-title">⚠️ 필독: 녹화 제한 안내</div>
            <div style="font-size: 15px; font-weight: 600;">
                보안 정책 및 <b>녹화 방지 기술(DRM, 화면 캡처 차단 등)</b>이 적용된 웹사이트는 시스템상 녹화가 불가능하거나 검은 화면으로 저장될 수 있습니다. 
                중요한 세미나의 경우 사전에 테스트 녹화를 권장합니다.
            </div>
        </div>
    """, unsafe_allow_html=True)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 ---
st.sidebar.markdown("### 🏗️ Daewoo E&C")
st.sidebar.markdown('#### Plant TI Team <span class="version-text">v1.4.2</span>', unsafe_allow_html=True)
st.sidebar.markdown("---")
admin_input = st.sidebar.text_input("Master Password", type="password")
is_admin = (admin_input == MASTER_PASSWORD)
menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.markdown('# 📅 웨비나 예약 현황 <span class="version-text">v1.4.2</span>', unsafe_allow_html=True)
    
    # 최상단 주의사항 배치
    show_caution_notice()
    
    with st.container(border=True):
        st.subheader("📝 신규 예약")
        title = st.text_input("1. 웨비나 명칭")
        url = st.text_input("2. 접속 URL")
        c1, c2 = st.columns(2)
        with c1: email = st.text_input("3. 확인용 이메일")
        with c2: pw = st.text_input("4. 삭제 비밀번호", type="password")
        
        c3, c4 = st.columns(2)
        with c3: zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c4: dur = st.number_input("6. 녹화 시간(분)", value=60)
        
        t_tz = pytz.timezone(WORLD_ZONES[zone])
        col_d, col_t = st.columns(2)
        with col_d: d_in = st.date_input("7. 현지 날짜")
        with col_t: t_in = st.time_input("8. 현지 시각")
        
        l_dt = t_tz.localize(datetime.combine(d_in, t_in))
        k_dt = l_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-box">
                <span style="color:{sub};">🚀 실제 녹화 시작 시각 (KST):</span><br>
                <span class="kst-highlight">{k_dt.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        chk = st.checkbox("✅ 정보 및 주의사항을 모두 확인했습니다.")
        if st.button("🚀 예약 확정", use_container_width=True):
            if chk and title and url:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url, "email": email, "scheduled_at": l_dt.isoformat(),
                    "duration_min": dur, "status": "pending", "timezone_name": zone, "delete_password": pw
                }).execute()
                st.success("예약 완료!")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 전체 예약 목록 (KST 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            c_kst = pd.to_datetime(item['created_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 URL: {item['webinar_url']}")
                st.markdown(f"🚀 **KST 시작:** {s_kst.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"📝 **신청 시각(KST):** {c_kst.strftime('%Y-%m-%d %H:%M')}")
                if item.get('failure_reason'):
                    st.error(f"🚨 에러 원인: {item['failure_reason']}")
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.markdown('# 🎥 녹화 결과 관리 <span class="version-text">v1.4.2</span>', unsafe_allow_html=True)
    
    # 결과 창에도 주의사항 배치
    show_caution_notice()
    
    res = supabase.table("webinar_reservations").select("*").order("created_at", desc=True).execute()
    
    found_data = False
    if res.data:
        for item in res.data:
            if item['status'] in ["completed", "error", "running"]:
                found_data = True
                s_kst = pd.to_datetime(item['scheduled_at']).astimezone(pytz.timezone('Asia/Seoul'))
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1, 1])
                    with c1:
                        st.subheader(f"📺 {item['title']}")
                        st.write(f"📅 녹화 시각(KST): {s_kst.strftime('%Y-%m-%d %H:%M')}")
                        if item['status'] == "completed":
                            st.success("✅ 녹화 성공")
                        elif item['status'] == "running":
                            st.info("⏺️ 녹화 진행 중...")
                        else:
                            st.error(f"❌ 실패 원인: {item.get('failure_reason', '알 수 없는 에러')}")
                    
                    with c2:
                        if item['status'] == "completed" and st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                    with c3:
                        if item['status'] == "completed" and item.get('video_url'):
                            response = requests.get(item['video_url'])
                            st.download_button(label="💾 노트북 저장", data=response.content, file_name=f"{item['title']}.webm", key=f"dl_{item['id']}")
                    
                    if is_admin:
                        if st.button("🗑️ 영구 삭제", key=f"adm_f_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", id).execute()
                            st.rerun()
    if not found_data:
        st.info("표시할 녹화 기록이 없습니다.")