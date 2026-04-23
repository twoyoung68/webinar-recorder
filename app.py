import streamlit as st
import json
import os
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client
import pytz

# --- 1. 페이지 및 시간대 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST)": "America/New_York",
    "미국 서부 (PST)": "America/Los_Angeles",
    "영국 (GMT)": "Europe/London",
    "독일/프랑스 (CET)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore"
}

# --- 2. CSS 스타일: 가시성 및 디자인 강화 ---
st.markdown("""
    <style>
    /* 사이드바 메인 제목: 군청색 & 볼드 */
    .sidebar-main-title {
        color: #000080 !important;
        font-size: 24px !important;
        font-weight: 800 !important;
        line-height: 1.2;
        margin-bottom: 5px !important;
    }
    /* 사이드바 메뉴(라디오 버튼) 3배 확대 */
    div[data-testid="stRadio"] label p {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #004a99 !important;
    }
    /* 선택 메뉴 강조 박스 */
    .menu-focus-box {
        font-size: 38px !important;
        font-weight: 900 !important;
        color: #FF5733 !important;
        text-align: center;
        border: 4px solid #FF5733;
        border-radius: 20px;
        padding: 15px;
        background-color: #FFF5F2;
        margin-top: 20px;
    }
    /* 구분선 */
    .sidebar-divider {
        border-top: 2px solid #ddd;
        margin: 15px 0;
    }
    /* 시간 강조 텍스트 */
    .time-label { font-weight: bold; color: #555; }
    .kst-start { color: #004a99; font-weight: 900; font-size: 18px; }
    .req-time { color: #28a745; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_connection()

# --- 4. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

menu = st.sidebar.radio(
    "Menu Selection",
    ["📅 예약 및 현황", "🎥 녹화 영상"],
    index=0
)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 및 실시간 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 예약 입력 (해외 현지 시각 기준)")
        with st.form("recording_form", clear_on_submit=True):
            webinar_title = st.text_input("웨비나 명칭", placeholder="예: Hydrogen_Seminar_2026")
            webinar_url = st.text_input("웨비나 접속 URL")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_zone_name = st.selectbox("개최지 타임존", list(WORLD_ZONES.keys()))
                duration = st.number_input("녹화 시간 (분)", min_value=1, value=60)
            with col2:
                target_tz = pytz.timezone(WORLD_ZONES[selected_zone_name])
                now_at_local = datetime.now(target_tz)
                local_date = st.date_input("현지 시작 날짜", now_at_local.date())
                local_time = st.time_input("현지 시작 시각", (now_at_local + timedelta(hours=1)).time())

            st.markdown("---")
            confirm_check = st.checkbox("입력한 웨비나 정보와 시간이 정확함을 확인했습니다.")
            
            submit = st.form_submit_button("🚀 예약 확정 (Schedule Now)")
            
            if submit:
                if not confirm_check:
                    st.warning("⚠️ 확인 체크박스를 선택해 주세요.")
                elif webinar_title and webinar_url:
                    # 현지 시각 저장
                    chosen_dt = target_tz.localize(datetime.combine(local_date, local_time))
                    data = {
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": chosen_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone_name
                    }
                    supabase.table("webinar_reservations").insert(data).execute()
                    st.success(f"✅ 예약 완료! (한국 시작 시각: {chosen_dt.astimezone(KST).strftime('%m-%d %H:%M')})")
                    st.rerun()
                else:
                    st.warning("⚠️ 정보(명칭/URL)를 모두 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (한국 시간 기준)")
    
    # 목록 가져오기
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            # 1. 녹화 시작 예정 시각 (KST)
            sched_dt = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            kst_start_str = sched_dt.strftime('%Y-%m-%d %H:%M')
            
            # 2. 예약 신청 시각 (KST) - DB의 created_at 활용
            created_dt = pd.to_datetime(item['created_at']).astimezone(KST)
            kst_req_str = created_dt.strftime('%m-%d %H:%M')
            
            # 3. 현지 시각 정보
            tz_name = item.get('timezone_name', '대한민국 (KST)')
            local_dt = sched_dt.astimezone(pytz.timezone(WORLD_ZONES.get(tz_name, 'Asia/Seoul')))
            local_start_str = local_dt.strftime('%Y-%m-%d %H:%M')

            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            # 목록 제목: [녹화 시작(KST)] 제목 (신청: MM-DD)
            with st.expander(f"{status_icon} [시작: {kst_start_str}] {item['title']} (신청: {kst_req_str})"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**🔗 URL:** {item['webinar_url']}")
                    st.markdown(f"""
                        <div style="background-color: #f8f9fa; padding: 12px; border-radius: 8px; border-left: 5px solid #004a99;">
                            <span class="time-label">🚀 녹화 시작 예정 (KST):</span> <span class="kst-start">{kst_start_str}</span><br>
                            <span class="time-label">📝 예약 신청 시각 (KST):</span> <span class="req-time">{kst_req_str} (노트북 시간 기준)</span><br>
                            <span class="time-label">📍 현지 시작 시각 ({tz_name}):</span> <span>{local_start_str}</span>
                        </div>
                    """, unsafe_allow_html=True)
                with col_b:
                    if st.button("🗑️ 삭제", key=f"del_{item['id']}", use_container_width=True):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("현재 대기 중인 예약이 없습니다.")

# --- 6. [메뉴 2] 녹화 영상 ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 영상 확인")
    st.info("💡 완료된 영상은 PC로 다운로드하여 확인하시기 바랍니다.")

    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.subheader(f"📺 {item['title']}")
                    finished_at = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
                    st.write(f"📅 녹화 완료 시각(KST): {finished_at}")
                
                with col_btn:
                    if item.get('video_url'):
                        st.markdown(f"""
                            <a href="{item['video_url']}" download target="_blank">
                                <button style="width: 100%; background-color: #FF5733; color: white; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer;">
                                    📥 다운로드
                                </button>
                            </a>
                        """, unsafe_allow_html=True)
    else:
        st.warning("아직 완료된 영상이 없습니다.")