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

# --- 2. 테마별 컬러 및 가독성 설정 (월요일 오전 업데이트 버전) ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)

if dark_mode:
    bg_color, main_text, sub_text = "#0e1117", "#FFFFFF", "#B0B0B0"
    preview_bg, preview_border = "#1e293b", "#3b82f6"
    sidebar_title, box_focus = "#4dabff", "#2d3748"
    err_bg, err_text = "#441a1a", "#ff9b9b"
else:
    bg_color, main_text, sub_text = "#FFFFFF", "#1A1A1A", "#555555"
    preview_bg, preview_border = "#F0F7FF", "#004a99"
    sidebar_title, box_focus = "#000080", "#FFF5F2"
    err_bg, err_text = "#ffdce0", "#d32f2f"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {main_text}; }}
    .sidebar-main-title {{ color: {sidebar_title} !important; font-size: 24px !important; font-weight: 800 !important; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {sidebar_title} !important; }}
    .menu-focus-box {{ font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: {box_focus}; margin-top: 20px; }}
    .time-preview-box {{ background-color: {preview_bg}; padding: 18px; border-radius: 12px; border: 2px solid {preview_border}; margin: 15px 0; }}
    .preview-kst {{ color: #FF5733; font-weight: 900; font-size: 24px; }}
    .error-reason-box {{ background-color: {err_bg}; color: {err_text}; padding: 12px; border-radius: 8px; border-left: 5px solid {err_text}; margin: 10px 0; font-size: 14px; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase = init_connection()

# --- 4. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)
st.sidebar.markdown('---')
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('---')
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="border-color:#004a99; color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 현황")
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        webinar_title = st.text_input("1. 웨비나 명칭")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        c_mail, c_pw = st.columns(2)
        with c_mail: user_email = st.text_input("3. 확인용 이메일 주소")
        with c_pw: del_pw = st.text_input("4. 삭제 비밀번호", type="password")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("6. 녹화 시간 (분)", min_value=1, value=60)
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        with col_d: l_date = st.date_input("7. 현지 날짜", datetime.now(target_tz).date())
        with col_t: l_time = st.time_input("8. 현지 시각", value=datetime.now(target_tz).time(), key="time_master")

        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        st.markdown(f"""<div class="time-preview-box"><span style="color:{sub_text};">🔍 <b>한국 시작 시각 확인:</b></span><br><span class="preview-kst">{kst_preview.strftime("%Y-%m-%d %H:%M")} (KST)</span></div>""", unsafe_allow_html=True)

        st.markdown("---")
        confirm_check = st.checkbox("✅ 위 정보와 한국 시작 시각이 정확함을 최종 확인했습니다.")
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check: st.warning("⚠️ '최종 확인' 체크박스를 선택해야 합니다.")
            elif webinar_title and webinar_url and del_pw:
                supabase.table("webinar_reservations").insert({
                    "title": webinar_title, "webinar_url": webinar_url, "email": user_email,
                    "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                    "status": "pending", "timezone_name": selected_zone, "delete_password": del_pw, "is_downloaded": False
                }).execute()
                st.success("✅ 예약 완료!")
                st.rerun()

    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            tz_n = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_n, 'Asia/Seoul'))
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 현지: {sched_local.strftime('%H:%M')}"):
                st.write(f"🔗 URL: {item['webinar_url']}")
                if item['status'] == "error":
                    st.markdown(f'<div class="error-reason-box">⚠️ 실패 원인: {item.get("failure_reason", "알 수 없는 오류")}</div>', unsafe_allow_html=True)
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 6. [메뉴 2] 녹화 영상 (실패 원인 분석 기능 추가) ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 결과 및 파일 관리")
    # 완료(completed)와 에러(error) 상태인 것을 모두 가져옵니다.
    res = supabase.table("webinar_reservations").select("*").in_("status", ["completed", "error"]).order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    if item['status'] == "completed":
                        st.markdown('<span style="background-color:#e8f5e9; color:#2e7d32; padding:5px 10px; border-radius:5px; font-weight:800;">✅ 녹화 성공</span>', unsafe_allow_html=True)
                        st.write("✅ 다운로드 완료" if item.get('is_downloaded') else "⏳ 수령 전")
                    else:
                        st.markdown('<span style="background-color:#ffebee; color:#c62828; padding:5px 10px; border-radius:5px; font-weight:800;">❌ 녹화 실패</span>', unsafe_allow_html=True)
                        # [핵심] 실패 원인을 사용자에게 보여줌
                        st.markdown(f'<div class="error-reason-box">🚨 원인 분석: {item.get("failure_reason", "데이터 없음 - 타임아웃 또는 강제 종료 가능성")}</div>', unsafe_allow_html=True)
                
                with c2:
                    if item['status'] == "completed" and st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                        supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                        st.rerun()
                
                with c3:
                    if item['status'] == "completed" and item.get('video_url'):
                        response = requests.get(item['video_url'])
                        st.download_button(label="💾 노트북 저장", data=response.content, file_name=f"{item['title']}.webm", mime="video/webm", key=f"dl_{item['id']}")
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else: st.info("기록된 녹화 결과가 없습니다.")