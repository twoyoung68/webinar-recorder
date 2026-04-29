# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.5.2 (2026-04-29)
# DESCRIPTION: Iframe Penetration & Diagnostic View (Based on Stable v1.4.4)
# ==========================================

import streamlit as st
import os
import pandas as pd
import requests
import pytz
from supabase import create_client
from datetime import datetime

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207" 

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

# --- [AI 주소 분석 함수] ---
def analyze_url_feasibility(url):
    if not url: return None, None
    url = url.lower()
    if any(x in url for x in ["zoom.us", "teams.microsoft", "webex.com"]):
        return "🔴 녹화 불가", "Zoom, Teams 등 전용 앱 실행이 필요한 플랫폼은 시스템상 접근이 제한됩니다."
    elif any(x in url for x in ["gasworld.tv", "linkedin.com", "facebook.com", "on24.com"]):
        return "🟠 주의 (로그인/보안)", "해당 사이트는 보안 장벽이 높습니다. 봇이 재생 버튼을 찾지 못할 경우 0바이트 파일이 생성될 수 있습니다."
    elif any(x in url for x in ["youtube.com", "vimeo.com"]):
        return "🟢 녹화 가능 (높음)", "공개 스트리밍 플랫폼입니다. 비교적 안정적인 녹화가 예상됩니다."
    else:
        return "🟡 확인 필요", "일반 웹페이지입니다. 보안 설정에 따라 결과가 달라질 수 있으니 짧은 테스트 녹화를 권장합니다."

# --- 2. 테마 및 스타일 설정 ---
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
    .time-box {{ background-color: {box}; padding: 18px; border-radius: 12px; border: 2px solid {pt}; margin: 15px 0; }}
    .kst-highlight {{ color: #FF5733; font-weight: 900; font-size: 24px; }}
    .version-tag {{ font-size: 14px !important; font-weight: normal !important; color: gray !important; vertical-align: bottom; margin-left: 10px; }}
    .caution-container {{
        background-color: {caution_bg}; border: 2px solid {caution_border};
        padding: 18px; border-radius: 10px; margin-bottom: 25px; color: {txt};
    }}
    .caution-title {{ color: #ff4b4b; font-weight: 900; font-size: 18px; margin-bottom: 8px; }}
    .diag-link {{ color: #4dabff; font-weight: 700; text-decoration: underline; }}
    </style>
""", unsafe_allow_html=True)

# 주의사항 출력 함수
def show_caution_notice():
    st.markdown(f"""
        <div class="caution-container">
            <div class="caution-title">⚠️ 필독: 시스템 녹화 제한 안내</div>
            <div style="font-size: 14px; line-height: 1.6;">
                본 시스템은 웹 브라우저 기반 자동화 도구입니다. 아래 플랫폼은 녹화가 어렵거나 불가능할 수 있습니다.
                <ul style="margin-top: 5px;">
                    <li><b>앱 실행 플랫폼:</b> Zoom, MS Teams, Webex (녹화 불가)</li>
                    <li><b>보안 보안/로그인:</b> Gasworld, LinkedIn 등 로그인이 필수인 사이트</li>
                    <li><b>복제 방지(DRM):</b> 유료 강의, OTT 서비스 등 (검은 화면 저장 가능성)</li>
                </ul>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Supabase 연결
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 구성 ---
st.sidebar.markdown("### 🏗️ Daewoo E&C")
st.sidebar.markdown(f'#### Plant TI Team <span class="version-tag">v1.5.2</span>', unsafe_allow_html=True)
st.sidebar.markdown('---')
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)
menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.markdown(f'# 📅 웨비나 예약 현황 <span class="version-tag">v1.5.2</span>', unsafe_allow_html=True)
    show_caution_notice()
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        title = st.text_input("1. 웨비나 명칭")
        url_input = st.text_input("2. 접속 URL")
        
        # AI 주소 분석 결과 표시
        status_tag, advice = analyze_url_feasibility(url_input)
        if status_tag:
            with st.chat_message("assistant"):
                st.markdown(f"**AI 분석 결과: {status_tag}**")
                st.caption(advice)
        
        c_mail, c_pw = st.columns(2)
        with c_mail: user_email = st.text_input("3. 확인용 이메일")
        with c_pw: del_pw = st.text_input("4. 삭제 비밀번호", type="password")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("6. 녹화 시간(분)", min_value=1, value=60)
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
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
            if chk and title and url_input and del_pw:
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input, "email": user_email,
                    "scheduled_at": rec_dt.isoformat(), "duration_min": duration,
                    "status": "pending", "timezone_name": selected_zone, "delete_password": del_pw
                }).execute()
                st.success("예약이 정상적으로 등록되었습니다!")
                st.rerun()
            else:
                st.warning("⚠️ 필수 항목 입력 및 최종 확인 체크가 필요합니다.")

    # 목록 표시
    st.markdown("---")
    st.subheader("📋 전체 예약 목록 (KST 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 URL: {item['webinar_url']}")
                st.markdown(f"🚀 **한국 녹화 시작:** {s_kst.strftime('%Y-%m-%d %H:%M')}")
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.markdown(f'# 🎥 녹화 결과 관리 <span class="version-text">v1.5.2</span>', unsafe_allow_html=True)
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
                        
                        # 진단용 스크린샷 링크 표시 (v1.5.2 핵심)
                        if item.get('failure_reason'):
                            reason = item['failure_reason']
                            if "진단샷: " in reason:
                                msg, url = reason.split(" / 진단샷: ")
                                st.write(f"ℹ️ {msg}")
                                st.markdown(f"📸 **[봇이 본 현장 화면 확인하기]({url})**")
                            else:
                                st.write(f"ℹ️ {reason}")
                        
                        if item['status'] == "completed": st.success("✅ 녹화 성공")
                        elif item['status'] == "running": st.info("⏺️ 녹화 진행 중...")
                    
                    with c2:
                        if item['status'] == "completed" and st.button("📥 확인", key=f"chk_{item['id']}"):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                    with c3:
                        if item['status'] == "completed" and item.get('video_url'):
                            response = requests.get(item['video_url'])
                            st.download_button(
                                label="💾 저장", 
                                data=response.content, 
                                file_name=f"{item['title']}.webm", 
                                mime="video/webm",
                                key=f"dl_{item['id']}"
                            )
                    if is_admin:
                        if st.button("🗑️ 영구 삭제", key=f"adm_f_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()