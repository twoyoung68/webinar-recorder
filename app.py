import streamlit as st
from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# ==========================================
# SECTION 1: 설정 및 데이터베이스 연결
# ==========================================
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

# 타임존 리스트 정의
TIMEZONES = {
    "일본/한국 (JST/KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "중앙 유럽 (CET/CEST)": "Europe/Berlin",
    "중국/싱가포르 (CST)": "Asia/Shanghai"
}

st.set_page_config(page_title="Global Webinar Recorder", layout="wide")
st.title("🌐 해외 세미나 스마트 예약 시스템")


# ==========================================
# SECTION 2: 예약 입력 UI (사용자 입력부)
# ==========================================
with st.container(border=True):
    st.subheader("📅 신규 세미나 등록")
    webinar_url = st.text_input("세미나 접속 URL", placeholder="https://example.com/webinar")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        local_date = st.date_input("현지 날짜", datetime.now().date())
        
    with col2:
        # [수정] 세션 상태를 사용하여 시간 입력 값 고정 및 5분 단위 설정
        if "selected_time" not in st.session_state:
            st.session_state["selected_time"] = datetime.now().time()
            
        local_time = st.time_input(
            "현지 시작 시각 (5분 단위)", 
            key="selected_time",
            step=300 
        )
        
    with col3:
        timezone_label = st.selectbox("현지 타임존 선택", list(TIMEZONES.keys()))

    # --- 시차 계산 로직 ---
    selected_tz = pytz.timezone(TIMEZONES[timezone_label])
    local_dt = datetime.combine(local_date, local_time)
    localized_dt = selected_tz.localize(local_dt)
    
    # 한국 시각(KST)으로 변환
    kst_dt = localized_dt.astimezone(pytz.timezone("Asia/Seoul"))
    
    st.info(f"💡 **한국 시각 환산:** {kst_dt.strftime('%Y-%m-%d %H:%M')} KST (이 시간에 녹화가 시작됩니다)")

    duration = st.number_input("녹화 지속 시간(분)", min_value=1, value=60)


# ==========================================
# SECTION 3: 데이터 저장 로직 (Supabase 전송)
# ==========================================
if st.button("🚀 예약 확정 및 서버 전송"):
        formatted_kst = kst_dt.isoformat()
        
        data = {
            "webinar_url": webinar_url,
            "scheduled_at": formatted_kst,
            "duration_min": duration,
            "status": "pending",
            "timezone_info": timezone_label
        }
        
        try:
            # 데이터 전송
            supabase.table("webinar_reservations").insert(data).execute()
            
            # 저장 성공 피드백 추가
            st.balloons() # 축하 풍선 효과
            st.success(f"✨ 저장 완료! [{kst_dt.strftime('%m/%d %H:%M')}] 녹화가 예약되었습니다.")
            
            # 2초 뒤 화면 새로고침 (목록 업데이트를 위해)
            import time
            time.sleep(2)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 저장 실패: {e}")


# ==========================================
# SECTION 4: 예약 목록 및 관리 (취소/상태 확인)
# ==========================================
st.divider()
st.subheader("📋 녹화 현황 및 결과물")

try:
    response = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(20).execute()
    
    if response.data:
        for item in response.data:
            status = item['status']
            
            # [수정] 9시간 오차 교정 표시 로직
            try:
                # DB에서 가져온 시간을 읽고 한국 시간으로 강제 변환
                raw_time = item['scheduled_at'].replace('Z', '+00:00')
                dt_obj = datetime.fromisoformat(raw_time)
                kst_display = dt_obj.astimezone(pytz.timezone("Asia/Seoul"))
                display_time = kst_display.strftime('%Y-%m-%d %H:%M')
            except:
                display_time = item['scheduled_at']

            status_style = {"pending": "📅 [대기 중]", "running": "⏳ [녹화 중]", "completed": "✅ [완료]", "failed": "❌ [실패]"}
            
            with st.expander(f"{status_style.get(status, status)} {item['webinar_url'][:40]}..."):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.write(f"**한국 시작 시간:** {display_time} KST")
                    st.write(f"**지속 시간:** {item['duration_min']}분")
                with c2:
                    st.write(f"**현지 타임존:** {item.get('timezone_info', 'N/A')}")
                with c3:
                    # 1. 예약 취소 버튼 (대기 중일 때만)
                    if status == "pending":
                        if st.button("🗑️ 예약 취소", key=f"del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.warning("예약이 삭제되었습니다.")
                            st.rerun()
                    
                    # 2. 다운로드 버튼 (녹화가 완료되어 video_url이 있을 때)
                    elif status == "completed":
                        video_url = item.get('video_url')
                        if video_url:
                            st.link_button("📥 녹화본 다운로드", video_url, type="primary") # 강조된 파란 버튼
                        else:
                            st.info("📂 파일 업로드 중...")
                    
                    # 3. 기타 상태 표시
                    elif status == "running":
                        st.warning("⏳ 녹화 중")
                    else:
                        st.error("❌ 녹화 실패")

    else:
        st.info("현재 등록된 예약 내역이 없습니다.")
except Exception as e:
    st.error(f"데이터 로드 오류: {e}")