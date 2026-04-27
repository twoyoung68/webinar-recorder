# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.4.4 (2026-04-28)
# DESCRIPTION: Detailed Platform Compatibility Caution
# UPDATED BY: Gemini Assistant (Based on v1.3.0 Stable)
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
MASTER_PASSWORD = "1207" # 플랜트TI 팀 고정 지침

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
    .caution-container {{
        background-color: {caution_bg}; border: 2px solid {caution_border};
        padding: 18px; border-radius: 10px; margin-bottom: 25px; color: {txt};
    }}
    .caution-title {{ color: #ff4b4b; font-weight: 900; font-size: 18px; margin-bottom: 8px; }}
    .caution-list {{ font-size: 14px; line-height: 1.6; margin-top: 5px; }}
    </style>
""", unsafe_allow_html=True)

# [v1.4.4 핵심] 주의사항 출력 함수 보강
def show_caution_notice():
    st.markdown(f"""
        <div class="caution-container">
            <div class="caution-title">⚠️ 필독: 시스템 녹화 제한 안내</div>
            <div class="caution-list">
                본 시스템은 웹 브라우저 기반 자동화 도구입니다. 아래와 같은 경우 녹화가 불가능하거나 정상적으로 작동하지 않습니다.
                <ul>
                    <li><b>전용 앱 실행 플랫폼:</b> <b>Zoom, MS Teams, Cisco Webex</b> 등 브라우저가 아닌 별도 앱 설치/실행을 강제하는 사이트 (녹화 불가)</li>
                    <li><b>강력한 봇 차단:</b> 로그인 시 로봇 방지(CAPTCHA)나 2차 인증을 요구하는 사이트</li>
                    <li><b>보안 컨텐츠(DRM):</b> 넷플릭스, 유료 강의 등 복제 방지 기술이 적용된 사이트 (검은 화면으로 저장됨)</li>
                </ul>
                <b>중요한 세미나는 반드시 사전에 5분 내외의 테스트 예약을 통해 녹화 가능 여부를 확인하십시오.</b>
            </div>
        </div>
    """, unsafe_allow_html=True)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 ---
st.sidebar.markdown("### 🏗️ Daewoo E&C")
st.sidebar.markdown(f'#### Plant TI Team <span class="version-text">v1.4.4</span>', unsafe_allow_html=True)
st.sidebar.markdown("---")
admin_input = st.sidebar.text_input("Master Password", type="password")
is_admin = (admin_input == MASTER_PASSWORD)
menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.markdown(f'# 📅 웨비나 예약 현황 <span class="version-text">v1.4.4</span>', unsafe_allow_html=True)
    show_caution_notice()
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        title = st.text_input("1. 웨비나 명칭")
        url = st.text_input("2. 접속 URL")
        c1, c2 = st.columns(2)
        with c1: email = st.text_input("3. 확인용 이메일")
        with c2: pw = st.text_input("4. 삭제 비밀번호", type="password")
        
        c3, c4 = st.columns(2)
        with c3: zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c4: dur = st.number_input("6. 녹화 시간(분)", value=60)
        
        target_tz = pytz.timezone(WORLD_ZONES[zone])
        col_d, col_t = st.columns(2)
        # 명칭 통일: 녹화 시작 날짜/시각
        with col_d: rec_date = st.date_input("7. 녹화 시작 날짜 (현지 기준)")
        with col_t: rec_time = st.time_input("8. 녹화 시작 시각 (현지 기준)")
        
        rec_dt = target_tz.localize(datetime.combine(rec_date, rec_time))
        k_dt = rec_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-box">
                <span style="color:{sub};">🚀 실제 녹화 시작 시각 (KST):</span><br>
                <span class="kst-highlight">{k_dt.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        chk = st.checkbox("✅ 입력 정보와 위의 플랫폼 제한 사항을 모두 확인했습니다.")
        if st.button("🚀 예약 확정", use_container_width=True):
            if chk and title and url:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url, "email": email, "scheduled_at": rec_dt.isoformat(),
                    "duration_min": dur, "status": "pending", "timezone_name": zone, "delete_password": pw
                }).execute()
                st.success("예약이 정상적으로 등록되었습니다!")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 전체 예약 목록 (KST 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 URL: {item['webinar_url']}")
                st.markdown(f"🚀 **한국 녹화 시작:** {s_kst.strftime('%Y-%m-%d %H:%M')}")
                if item.get('failure_reason'):
                    st.error(f"🚨 에러 원인: {item['failure_reason']}")
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.markdown(f'# 🎥 녹화 결과 관리 <span class="version-text">v1.4.4</span>', unsafe_allow_html=True)
    show_caution_notice()
    
    res = supabase.table("webinar_reservations").select("*").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            if item['status'] in ["completed", "error", "running"]:
                s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
                with st.container(border=True):
                    c1, c2, c3 = st.columns([4, 1, 1])
                    with c1:
                        st.subheader(f"📺 {item['title']}")
                        st.write(f"📅 녹화 시각(KST): {s_kst.strftime('%Y-%m-%d %H:%M')}")
                        if item['status'] == "completed": st.success("✅ 녹화 성공")
                        elif item['status'] == "running": st.info("⏺️ 녹화 진행 중...")
                        else: st.error(f"❌ 실패 원인: {item.get('failure_reason', '알 수 없는 에러')}")
                    
                    with c2:
                        if item['status'] == "completed" and st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                    with c3:
                        if item['status'] == "completed" and item.get('video_url'):
                            response = requests.get(item['video_url'])
                            st.download_button(
                                label="💾 노트북 저장", 
                                data=response.content, 
                                file_name=f"{item['title']}.webm", 
                                mime="video/webm",
                                key=f"dl_{item['id']}"
                            )