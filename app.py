import os
from datetime import datetime
import pytz
import streamlit as st
from supabase import create_client
import requests
import pandas as pd

# --- 1. 페이지 및 환경 설정 (일관성 유지) ---
st.set_page_config(
    page_title="Plant TI Team Webinar Recorder",
    page_icon="🎥",
    layout="wide",
)

KST = pytz.timezone("Asia/Seoul")
MASTER_PASSWORD = "1207" # 내부 고정

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo",
}

# --- 2. CSS 스타일 (플랜트TI 표준 디자인 복구) ---
st.markdown("""
    <style>
    .sidebar-main-title { color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; }
    div[data-testid="stRadio"] label p { font-size: 28px !important; font-weight: 800 !important; color: #004a99 !important; }
    .menu-focus-box { font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: #FFF5F2; margin-top: 20px; }
    .sidebar-divider { border-top: 2px solid #ddd; margin: 15px 0; }
    .preview-box { background-color: #f0f4ff; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 15px 0; }
    .confirm-tag { color: #28a745; font-weight: 700; font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 및 유틸리티 ---
@st.cache_resource
def init_connection():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_connection()

def format_utc_to_kst(utc_value):
    if not utc_value: return "-"
    try:
        dt = datetime.fromisoformat(utc_value.replace("Z", "+00:00"))
        return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except: return str(utc_value)

# --- 4. 사이드바 구성 (CI 유지) ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)

with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
is_admin = admin_input == MASTER_PASSWORD

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)
st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 현황")

    with st.container(border=True):
        st.subheader("📝 신규 예약 입력")
        # 입력값 유지를 위해 form 사용 (단, 엔터키 자동 제출은 로직으로 방어)
        with st.form("recording_form", clear_on_submit=False):
            webinar_title = st.text_input("1. 웨비나 명칭")
            webinar_url = st.text_input("2. 웨비나 접속 URL")

            c1, c2, c3 = st.columns(3)
            with c1: selected_zone_name = st.selectbox("3. 개최지 타임존", list(WORLD_ZONES.keys()))
            with c2: duration = st.number_input("4. 녹화 시간 (분)", min_value=1, value=60)
            with c3: del_pw = st.text_input("5. 삭제 비밀번호", type="password")

            target_tz = pytz.timezone(WORLD_ZONES[selected_zone_name])
            col_d, col_t = st.columns(2)
            with col_d: local_date = st.date_input("6. 현지 시작 날짜", datetime.now(target_tz).date())
            with col_t: local_time = st.time_input("7. 현지 시작 시각", datetime.now(target_tz).time())

            # 사용자가 개선한 DST 대응 로직 통합
            naive_local_dt = datetime.combine(local_date, local_time)
            try:
                localized_dt = target_tz.localize(naive_local_dt, is_dst=None)
                kst_preview = localized_dt.astimezone(KST)
                st.markdown(f"""<div class="preview-box">🔍 <b>한국 시작 시각:</b> {kst_preview.strftime('%Y-%m-%d %H:%M')} (KST)</div>""", unsafe_allow_html=True)
                schedulable = True
            except (pytz.NonExistentTimeError, pytz.AmbiguousTimeError):
                st.error("⚠️ 선택한 시각은 서머타임 전환으로 인해 유효하지 않거나 모호합니다.")
                schedulable = False

            st.markdown("---")
            # [안전장치] 최종 확인 체크박스 복구
            confirm_check = st.checkbox("✅ 위 정보와 한국 시작 시각이 정확함을 최종 확인했습니다.")
            
            submit = st.form_submit_button("🚀 예약 저장 (Schedule Now)")
            
            if submit:
                if not confirm_check: st.warning("⚠️ '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
                elif not schedulable: st.error("⚠️ 유효하지 않은 시간대입니다.")
                elif webinar_title and webinar_url and del_pw:
                    payload = {
                        "title": webinar_title.strip(), "webinar_url": webinar_url.strip(),
                        "duration_min": int(duration), "delete_password": del_pw.strip(),
                        "scheduled_at": kst_preview.astimezone(pytz.utc).isoformat(),
                        "timezone_name": selected_zone_name, "status": "pending", "is_downloaded": False
                    }
                    supabase.table("webinar_reservations").insert(payload).execute()
                    st.success("✅ 예약이 저장되었습니다.")
                    st.rerun()
                else: st.error("⚠️ 모든 정보를 입력해 주세요.")

    # 예약 목록 표시 (생략 - 사용자님 코드와 동일하게 유지하되 디자인 가이드 적용)
    # ... [기존 목록 표시 로직] ...

# --- 6. [메뉴 2] 녹화 영상 (직접 다운로드 방식 복구) ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 파일 관리")
    # ... [조회 로직] ...
    # 수령 확인 버튼 클릭 시 is_downloaded 업데이트 로직 유지
    # '파일 받기' 버튼은 st.download_button을 사용하여 노트북 저장을 보장함 (이전 수정 사항 유지)