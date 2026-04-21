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

# --- 2. CSS 스타일: 가시성 극대화 및 대우건설 컬러 적용 ---
st.markdown("""
    <style>
    /* 사이드바 메뉴 선택 시 나타나는 거대 텍스트 스타일 (3배 크기) */
    .big-menu-title {
        font-size: 45px !important; 
        font-weight: 900 !important;
        color: #FF5733 !important; /* 대우 오렌지 포인트 */
        line-height: 1.2;
        margin: 25px 0;
        text-align: center;
        border: 3px solid #FF5733;
        border-radius: 15px;
        padding: 10px;
        background-color: #FFF5F2;
    }
    /* 사이드바 기본 라디오 버튼 글자 크기 조정 */
    div[data-testid="stSidebarNav"] {display: none;} /* 기본 네비게이션 숨김 */
    .stRadio [data-testid="stWidgetLabel"] p {
        font-size: 22px !important;
        font-weight: 800 !important;
        color: #004a99 !important; /* 대우 블루 */
    }
    /* 버튼 스타일 조정 */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
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
st.sidebar.image("https://www.daewooenc.com/images/common/logo.png", width=180)
st.sidebar.markdown("### **Plant TI Webinar**")

menu = st.sidebar.radio(
    "Menu Selection",
    ["📅 예약 및 현황 관리", "🎥 녹화 영상 확인"],
    index=0
)

st.sidebar.markdown("---")

# 사이드바 하단 거대 아이콘 표시
if menu == "🎥 녹화 영상 확인":
    st.sidebar.markdown('<p class="big-menu-title">🎥<br>녹화영상<br>확인</p>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<p class="big-menu-title" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>웨비나<br>예약</p>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 관리 ---
if menu == "📅 예약 및 현황 관리":
    st.title("📅 웨비나 녹화 예약 시스템")
    
    # 예약 입력 폼
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약")
        with st.form("recording_form", clear_on_submit=True):
            webinar_title = st.text_input("웨비나 명칭", placeholder="예: Hydrogen_Tech_Seminar")
            webinar_url = st.text_input("웨비나 접속 URL (https://...)")
            
            col1, col2 = st.columns(2)
            with col1:
                selected_zone = st.selectbox("개최지 타임존", list(WORLD_ZONES.keys()))
                duration = st.number_input("녹화 시간 (분 단위)", min_value=1, value=60, step=10)
            
            with col2:
                target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
                now_at = datetime.now(target_tz)
                local_date = st.date_input("현지 날짜", now_at.date())
                local_time = st.time_input("현지 시각", now_at.time())

            submit = st.form_submit_button("🚀 예약 확정 (Schedule Now)")
            
            if submit:
                if webinar_title and webinar_url:
                    # 현지 시각을 UTC로 변환하여 저장
                    chosen_dt = target_tz.localize(datetime.combine(local_date, local_time))
                    if chosen_dt < datetime.now(target_tz):
                        st.error("📍 과거 시간으로는 예약할 수 없습니다.")
                    else:
                        data = {
                            "title": webinar_title,
                            "webinar_url": webinar_url,
                            "scheduled_at": chosen_dt.isoformat(),
                            "duration_min": duration,
                            "status": "pending",
                            "timezone_name": selected_zone
                        }
                        supabase.table("webinar_reservations").insert(data).execute()
                        st.success(f"✅ '{webinar_title}' 예약 완료!")
                        st.rerun()
                else:
                    st.warning("⚠️ 명칭과 URL을 입력해 주세요.")

    st.markdown("---")
    
    # 현황 목록
    st.subheader("📋 실시간 예약 및 녹화 현황")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            # 상태별 아이콘 및 텍스트
            status = item['status']
            if status == "pending":
                s_icon, s_label, s_color = "⏳", "대기 중", "blue"
            elif status == "running":
                s_icon, s_label, s_color = "⏺️", "녹화 중", "orange"
            elif status == "completed":
                s_icon, s_label, s_color = "✅", "완료됨", "green"
            else:
                s_icon, s_label, s_color = "❌", "에러", "red"
            
            # 시간 포맷팅
            dt_obj = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            kst_time = dt_obj.strftime('%Y-%m-%d %H:%M')
            
            with st.expander(f"{s_icon} [{s_label}] {item['title']} (KST: {kst_time})"):
                st.markdown(f"**🔗 접속 주소:** {item['webinar_url']}")
                st.write(f"⏱️ **녹화 시간:** {item['duration_min']}분 | 📍 **설정 타임존:** {item.get('timezone_name')}")
                
                if st.button("🗑️ 예약 삭제", key=f"del_{item['id']}", help="데이터베이스에서 삭제합니다."):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()
    else:
        st.info("현재 대기 중인 예약이 없습니다.")

# --- 6. [메뉴 2] 녹화 영상 확인 ---
elif menu == "🎥 녹화 영상 확인":
    st.title("🎥 녹화 완료 영상 확인")
    st.markdown("##### 완료된 영상은 Google Cloud Storage(GCS)에서 즉시 조회 가능합니다.")
    st.write("")

    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([4, 1])
                with col_info:
                    st.subheader(f"📺 {item['title']}")
                    # 생성 시간을 한국 시간으로 변환
                    finished_at = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
                    st.write(f"📅 **녹화 일시:** {finished_at}")
                    st.caption(f"ID: {item['id']}")
                
                with col_btn:
                    video_url = item.get('video_url')
                    if video_url:
                        st.write("") # 간격 조절
                        st.link_button("📂 영상 보기", video_url, use_container_width=True)
                    else:
                        st.button("🚫 링크 없음", disabled=True, use_container_width=True)
    else:
        st.warning("아직 완료된 녹화 영상이 존재하지 않습니다.")