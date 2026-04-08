import streamlit as st
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# 1. 환경 변수 로드 및 Supabase 연결
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    st.error("⚠️ .env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요!")
    st.stop()

@st.cache_resource
def get_supabase():
    return create_client(url, key)

supabase = get_supabase()

# 화면 설정
st.set_page_config(page_title="Global Webinar Recorder", layout="wide")

# 2. 타임존 리스트 설정
TIMEZONES = {
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "중앙 유럽 (CET/CEST)": "Europe/Berlin",
    "일본/한국 (JST/KST)": "Asia/Seoul",
    "중국/싱가포르 (CST)": "Asia/Shanghai"
}

st.title("🌐 해외 세미나 스마트 예약 시스템")

# --- 예약 입력 섹션 ---
with st.container(border=True):
    st.subheader("📅 신규 세미나 등록")
    webinar_url = st.text_input("세미나 접속 URL (Zoom, YouTube, Web 등)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        local_date = st.date_input("현지 날짜", datetime.now().date())
    with col2:
        local_time = st.time_input("현지 시작 시각", datetime.now().time())
    with col3:
        timezone_label = st.selectbox("현지 타임존 선택", list(TIMEZONES.keys()))

    # --- 시차 계산 로직 ---
    selected_tz = pytz.timezone(TIMEZONES[timezone_label])
    local_dt = datetime.combine(local_date, local_time)
    # 1. 현지 시각 정보 부여
    localized_dt = selected_tz.localize(local_dt)
    # 2. 한국 시각(KST)으로 변환
    kst_dt = localized_dt.astimezone(pytz.timezone("Asia/Seoul"))
    
    st.info(f"💡 **한국 시각 환산:** {kst_dt.strftime('%Y-%m-%d %H:%M')} KST (이 시간에 녹화가 시작됩니다)")

    duration = st.number_input("녹화 지속 시간(분)", min_value=1, value=60)
    
    if st.button("🚀 예약 확정 및 서버 전송"):
        data = {
            "webinar_url": webinar_url,
            "scheduled_at": kst_dt.isoformat(), # 한국 시각 기준으로 저장
            "duration_min": duration,
            "status": "pending",
            "timezone_info": timezone_label
        }
        try:
            supabase.table("webinar_reservations").insert(data).execute()
            st.success("✅ 예약이 완료되었습니다! 시스템이 시간에 맞춰 깨어납니다.")
            st.rerun()
        except Exception as e:
            st.error(f"저장 실패: {e}")

# --- 예약 및 결과 목록 섹션 ---
st.divider()
st.subheader("📋 녹화 현황 및 결과물")

try:
    # 최근 예약 20개 가져오기
    response = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(20).execute()
    
    if response.data:
        for item in response.data:
            # 상태에 따른 색상/아이콘 결정
            status = item['status']
            status_map = {
                "pending": {"icon": "📅", "label": "대기 중", "color": "blue"},
                "running": {"icon": "⏳", "label": "녹화 중", "color": "orange"},
                "completed": {"icon": "✅", "label": "완료", "color": "green"},
                "failed": {"icon": "❌", "label": "실패", "color": "red"}
            }
            s = status_map.get(status, status_map["pending"])
            
            with st.expander(f"{s['icon']} [{s['label']}] {item['webinar_url'][:50]}..."):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**한국 시작 시간:** {item['scheduled_at']}")
                    st.write(f"**지속 시간:** {item['duration_min']}분")
                with c2:
                    st.write(f"**현지 타임존:** {item.get('timezone_info', '알 수 없음')}")
                with c3:
                    if status == "completed" and item.get('video_url'):
                        st.link_button("📥 다운로드", item['video_url'])
                    else:
                        st.button("다운로드 불가", disabled=True, key=item['id'])
    else:
        st.info("현재 등록된 예약 내역이 없습니다.")
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")