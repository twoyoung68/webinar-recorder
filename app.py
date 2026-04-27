# ==========================================
# SYSTEM: Plant TI Team Webinar Recorder
# VERSION: v1.4.1 (2026-04-27)
# DESCRIPTION: Fixed Time Input Reset Bug
# ==========================================

import streamlit as st
import os
import pandas as pd
import requests
import pytz
from supabase import create_client
from datetime import datetime, time

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207" # 플랜트TI 팀 내부 지침

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
    .version-tag {{ font-size: 12px !important; font-weight: normal !important; color: gray !important; vertical-align: bottom; margin-left: 8px; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {pt} !important; }}
    .time-preview-box {{ background-color: {box}; padding: 18px; border-radius: 12px; border: 2px solid {pt}; margin: 15px 0; }}
    .preview-kst {{ color: #FF5733; font-weight: 900; font-size: 24px; }}
    .kst-label {{ color: #28a745; font-weight: 800; font-size: 16px; }}
    .error-reason-box {{ background-color: {err_bg}; color: {err_text}; padding: 12px; border-radius: 8px; border-left: 5px solid {err_text}; margin: 10px 0; font-size: 14px; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

# Supabase 연결
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- 3. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown(f'<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder <span class="version-tag">v1.4.1</span></p>', unsafe_allow_html=True)

st.sidebar.markdown('---')
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('---')
menu = st.sidebar.radio("메뉴 선택", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 4. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.markdown(f'# 📅 웨비나 예약 현황 <span class="version-tag" style="font-size:16px;">v1.4.1</span>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        webinar_title = st.text_input("1. 웨비나 명칭")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        c_mail, c_pw = st.columns(2)
        with c_mail: user_email = st.text_input("3. 확인용 이메일 주소")
        with c_pw: del_pw = st.text_input("4. 삭제 비밀번호", type="password")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("6. 녹화 시간(분)", min_value=1, value=60)
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        
        # [해결 핵심] 세션 내에서 한 번만 초기화하여 리셋 방지
        if 'init_rec_dt' not in st.session_state:
            st.session_state.init_rec_dt = datetime.now(target_tz)

        # 사용자가 입력 필드를 직접 수정할 수 있도록 value를 안정적으로 관리
        with col_d: 
            rec_date = st.date_input("7. 녹화 시작 날짜 (개최지 기준)", value=st.session_state.init_rec_dt.date())
        with col_t: 
            rec_time = st.time_input("8. 녹화 시작 시각 (개최지 기준)", value=st.session_state.init_rec_dt.time())

        # 녹화 시각 변환 (입력된 값 기준)
        rec_dt = target_tz.localize(datetime.combine(rec_date, rec_time))
        kst_preview = rec_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-preview-box">
                <span style="color:{sub}; font-size:14px;">🔍 <b>설정된 녹화 시각 (현지):</b> {rec_date} {rec_time.strftime('%H:%M')} ({selected_zone})</span><br>
                <span class="kst-label">🚀 실제 녹화 시작 시각 (한국 KST):</span><br>
                <span class="preview-kst">{kst_preview.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        confirm_check = st.checkbox("✅ 입력한 녹화 시각 및 한국 시작 시간이 정확함을 최종 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
            elif webinar_title and webinar_url and del_pw:
                supabase.table("webinar_reservations").insert({
                    "title": webinar_title, 
                    "webinar_url": webinar_url, 
                    "email": user_email,
                    "scheduled_at": rec_dt.isoformat(), 
                    "duration_min": duration,
                    "status": "pending", 
                    "timezone_name": selected_zone, 
                    "delete_password": del_pw, 
                    "is_downloaded": False
                }).execute()
                
                st.success("✅ 예약이 성공적으로 등록되었습니다.")
                # 성공 시 세션 초기값 삭제 및 새로고침
                del st.session_state.init_rec_dt
                st.rerun()
            else:
                st.error("⚠️ 모든 필수 항목을 입력해 주세요.")

    # 목록 표시 로직 (기존 v1.4.0과 동일)
    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            tz_n = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_n, 'Asia/Seoul'))
            s_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)

            with st.expander(f"[{item['status'].upper()}] {item['title']} | KST 시작: {s_kst.strftime('%m-%d %H:%M')}"):
                col_i, col_d = st.columns([4, 1])
                with col_i:
                    st.write(f"🔗 URL: {item['webinar_url']}")
                    st.write(f"🌍 **현지 녹화 시각:** {s_local.strftime('%Y-%m-%d %H:%M')} ({tz_n})")
                    st.markdown(f"🚀 **한국 녹화 시각:** <span style='color:#FF5733; font-weight:800;'>{s_kst.strftime('%Y-%m-%d %H:%M')} (KST)</span>", unsafe_allow_html=True)
                    if item.get('failure_reason'):
                        st.markdown(f'<div class="error-reason-box">🚨 실패 원인: {item["failure_reason"]}</div>', unsafe_allow_html=True)
                with col_d:
                    if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()

# --- 5. [메뉴 2] 녹화 완료 파일 (v1.4.0 유지) ---
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
                        else: st.error(f"❌ 실패 원인: {item.get('failure_reason', '알 수 없는 에러')}")
                    
                    with c2:
                        if item['status'] == "completed" and st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                    with c3:
                        if item['status'] == "completed" and item.get('video_url'):
                            response = requests.get(item['video_url'])
                            st.download_button(label="💾 노트북 저장", data=response.content, file_name=f"{item['title']}.webm", key=f"dl_{item['id']}")