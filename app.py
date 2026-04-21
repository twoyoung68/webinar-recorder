import streamlit as st
import json
import os
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client
import pytz

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="Plant TI Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST)": "America/New_York",
    "미국 서부 (PST)": "America/Los_Angeles",
    "영국 (GMT)": "Europe/London",
    "독일/프랑스 (CET)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore"
}

# --- 2. CSS 스타일: 메뉴 라벨 3배 강화 및 UI 최적화 ---
st.markdown("""
    <style>
    /* 1. 사이드바 메뉴 라벨(글자) 크기 3배 확대 */
    .stRadio [data-testid="stWidgetLabel"] p {
        font-size: 24px !important;
        font-weight: 800 !important;
        color: #004a99 !important;
        margin-bottom: 15px !important;
    }
    
    /* 2. 실제 라디오 버튼 선택지 글자 크기 확대 */
    div[data-testid="stRadio"] label p {
        font-size: 32px !important; /* 3배 수준으로 확대 */
        font-weight: 700 !important;
        line-height: 1.5 !important;
        padding: 10px 0 !important;
    }

    /* 3. 사이드바 하단 강조 박스 */
    .menu-focus-box {
        font-size: 40px !important;
        font-weight: 900 !important;
        color: #FF5733 !important;
        text-align: center;
        border: 4px solid #FF5733;
        border-radius: 20px;
        padding: 15px;
        background-color: #FFF5F2;
        margin-top: 30px;
    }
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
# 로고 에러 방지를 위해 텍스트와 함께 배치
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown("### **Plant TI Webinar**")
st.sidebar.write("")

# [요청사항] 이 부분의 글자가 큼직하게 나옵니다.
menu = st.sidebar.radio(
    "Menu Selection",
    ["📅 예약 및 현황 관리", "🎥 녹화 영상 확인"],
    index=0
)

st.sidebar.markdown("---")

# 현재 메뉴 상태를 하단에 한 번 더 거대하게 표시
if menu == "🎥 녹화 영상 확인":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>영상<br>확인</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>녹화<br>예약</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 관리 ---
if menu == "📅 예약 및 현황 관리":
    st.title("📅 웨비나 녹화 예약 및 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 예약 입력")
        with st.form("recording_form"):
            webinar_title = st.text_input("웨비나 명칭", placeholder="예: Hydrogen_Seminar_2026")
            webinar_url = st.text_input("웨비나 접속 URL")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_zone = st.selectbox("개최지 타임존", list(WORLD_ZONES.keys()))
                duration = st.number_input("녹화 시간 (분)", min_value=1, value=60)
            with col2:
                target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
                now_at = datetime.now(target_tz)
                local_date = st.date_input("현지 날짜", now_at.date())
                local_time = st.time_input("현지 시각", now_at.time())

            if st.form_submit_button("🚀 예약 확정"):
                if webinar_title and webinar_url:
                    chosen_dt = target_tz.localize(datetime.combine(local_date, local_time))
                    data = {
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": chosen_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone
                    }
                    supabase.table("webinar_reservations").insert(data).execute()
                    st.success("✅ 예약이 완료되었습니다!")
                    st.rerun()

    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).execute()
    if res.data:
        for item in res.data:
            with st.expander(f"[{item['status'].upper()}] {item['title']}"):
                st.write(f"🔗 {item['webinar_url']}")
                if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 6. [메뉴 2] 녹화 영상 확인 (다운로드 방식) ---
elif menu == "🎥 녹화 영상 확인":
    st.title("🎥 녹화 완료 영상 리스트")
    st.info("💡 영상 보기 에러 방지를 위해 '직접 다운로드' 버튼으로 변경되었습니다.")

    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.subheader(f"📺 {item['title']}")
                    kst_finish = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
                    st.write(f"📅 녹화완료: {kst_finish}")
                
                with col_btn:
                    video_url = item.get('video_url')
                    if video_url:
                        # [요청사항] 영상 보기 대신 다운로드 방식으로 유도
                        # GCS URL 뒤에 파라미터를 붙여 다운로드를 강제하거나 가이드 제공
                        st.markdown(f"""
                            <a href="{video_url}" download target="_blank">
                                <button style="
                                    width: 100%;
                                    background-color: #FF5733;
                                    color: white;
                                    padding: 10px;
                                    border: none;
                                    border-radius: 5px;
                                    font-weight: bold;
                                    cursor: pointer;">
                                    📥 영상 다운로드
                                </button>
                            </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.write("링크 없음")
    else:
        st.warning("아직 완료된 영상이 없습니다.")