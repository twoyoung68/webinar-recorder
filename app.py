# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.3.2 (2026-04-27)
# DESCRIPTION: Title Versioning & Auto-reset Checkbox
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

# --- 2. 테마별 컬러 및 가독성 설정 ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)

if dark_mode:
    bg, txt, sub = "#0e1117", "#FFFFFF", "#B0B0B0"
    pt = "#4dabff"
    box = "#2d3748"
    err_bg, err_text = "#441a1a", "#ff9b9b"
else:
    bg, txt, sub = "#FFFFFF", "#1A1A1A", "#555555"
    pt = "#000080"
    box = "#F0F7FF"
    err_bg, err_text = "#ffdce0", "#d32f2f"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg}; color: {txt}; }}
    .sidebar-main-title {{ color: {pt} !important; font-size: 24px !important; font-weight: 800 !important; }}
    .version-text {{ font-size: 12px !important; font-weight: normal !important; color: gray !important; vertical-align: bottom; margin-left: 8px; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {pt} !important; }}
    .time-preview-box {{ background-color: {box}; padding: 18px; border-radius: 12px; border: 2px solid {pt}; margin: 15px 0; }}
    .preview-kst {{ color: #FF5733; font-weight: 900; font-size: 24px; }}
    .error-reason-box {{ background-color: {err_bg}; color: {err_text}; padding: 12px; border-radius: 8px; border-left: 5px solid {err_text}; margin: 10px 0; font-size: 14px; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
# 사이드바 타이틀 옆 버전 표시
st.sidebar.markdown(f'<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder <span class="version-text">v1.3.2</span></p>', unsafe_allow_html=True)

st.sidebar.markdown('---')
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('---')
menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    # 메인 타이틀 옆 버전 표시
    st.markdown(f'# 📅 글로벌 웨비나 예약 및 현황 <span class="version-text" style="font-size:16px;">v1.3.2</span>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        webinar_title = st.text_input("1. 웨비나 명칭", key="in_title")
        webinar_url = st.text_input("2. 웨비나 접속 URL", key="in_url")
        
        c_mail, c_pw = st.columns(2)
        with c_mail: user_email = st.text_input("3. 확인용 이메일 주소", key="in_email")
        with c_pw: del_pw = st.text_input("4. 삭제 비밀번호", type="password", key="in_del_pw")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()), key="in_zone")
        with c2: duration = st.number_input("6. 녹화 시간(분)", min_value=1, value=60, key="in_dur")
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        with col_d: l_date = st.date_input("7. 현지 날짜", datetime.now(target_tz).date(), key="in_date")
        with col_t: l_time = st.time_input("8. 현지 시각", value=datetime.now(target_tz).time(), key="in_time")

        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-preview-box">
                <span style="color:{sub}; font-size:14px;">🔍 <b>실제 녹화 시작 시각 (한국 기준):</b></span><br>
                <span class="preview-kst">{kst_preview.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        # [수정] 초기화를 위해 key 추가
        confirm_check = st.checkbox("✅ 위 정보와 한국 시작 시각이 정확함을 최종 확인했습니다.", key="confirm_check_box")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
            elif webinar_title and webinar_url and del_pw:
                supabase.table("webinar_reservations").insert({
                    "title": webinar_title, "webinar_url": webinar_url, "email": user_email,
                    "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                    "status": "pending", "timezone_name": selected_zone, "delete_password": del_pw, "is_downloaded": False
                }).execute()
                
                st.success("✅ 예약이 성공적으로 등록되었습니다.")
                
                # [핵심] 예약 확정 후 체크박스 상태 초기화
                st.session_state['confirm_check_box'] = False
                st.rerun()
            else:
                st.error("⚠️ 누락된 항목을 모두 입력해 주세요.")

    # 목록 표시 로직 (기존과 동일)
    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {s_kst.strftime('%m-%d %H:%M')}"):
                st.write(f"🔗 URL: {item['webinar_url']}")
                if item.get('failure_reason'):
                    st.markdown(f'<div class="error-reason-box">🚨 원인: {item["failure_reason"]}</div>', unsafe_allow_html=True)
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 (v1.3.0 로직 유지) ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과 관리")
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
                        else: st.error(f"❌ 실패: {item.get('failure_reason', '알 수 없는 에러')}")
                    
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
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()