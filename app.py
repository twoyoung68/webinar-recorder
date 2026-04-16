# [Section 1: 라이브러리 로드 및 설정]
import streamlit as st
import firebase_admin
from firebase_admin import credentials, storage
from supabase import create_client
import os
import json
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- Firebase 초기화 로직 ---
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    
    if firebase_json:
        try:
            # 환경 변수의 JSON 텍스트를 파싱하여 인증
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
        except Exception as e:
            st.error(f"⚠️ Firebase 설정 오류: JSON 형식을 확인하세요. ({e})")
            st.stop()
    else:
        # 로컬 환경: 파일에서 읽기
        if os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
        else:
            st.error("❌ Firebase 키 파일이 없습니다. 환경 변수나 파일을 확인하세요.")
            st.stop()

    firebase_admin.initialize_app(cred, {
        'storageBucket': 'webinar-recorder.firebasestorage.app'
    })

bucket = storage.bucket()
KST = pytz.timezone('Asia/Seoul')

# 타임존 리스트 (정확한 변환을 위한 딕셔너리)
TIMEZONES = {
    "한국 (KST)": "Asia/Seoul",
    "미국 (동부/EST)": "US/Eastern",
    "미국 (서부/PST)": "US/Pacific",
    "영국 (GMT/BST)": "Europe/London",
    "캐나다 (동부/EST)": "Canada/Eastern",
    "독일 (CET/CEST)": "Europe/Berlin"
}

st.set_page_config(page_title="Global Cloud Recorder", layout="wide")

# [Section 2: 상단 안내]
st.title("🌐 글로벌 세미나 클라우드 녹화 센터")
st.info("해외 현지 시간을 입력하면 시스템이 자동으로 서버 시간(UTC)으로 변환하고 한국 시간을 계산합니다.")

# [Section 3: 현지 시간 기반 예약 및 상태 유지]
st.divider()
with st.container(border=True):
    st.subheader("📅 새 녹화 작업 예약")
    
    web_url = st.text_input("웨비나 접속 URL", placeholder="https://...", key="url_input_unique")
    
    col1, col2, col3 = st.columns([1.5, 2, 1])
    
    with col1:
        tz_choice = st.selectbox("🌍 현지 타임존 선택", list(TIMEZONES.keys()), key="tz_select")
        # [핵심 수정] 사용자가 선택한 타임존을 실제로 적용합니다.
        selected_tz = pytz.timezone(TIMEZONES[tz_choice]) 
    
    with col2:
        # 현재 선택된 타임존의 실시간 시간을 가져옵니다.
        now_local = datetime.now(selected_tz)
        
        # 타임존이 바뀌었을 때만 초기 시간을 해당 국가 시간으로 갱신
        if "prev_tz" not in st.session_state or st.session_state.prev_tz != tz_choice:
            st.session_state.init_date = now_local.date()
            st.session_state.init_time = now_local.time()
            st.session_state.prev_tz = tz_choice

        c_date, c_time = st.columns(2)
        date = c_date.date_input("현지 날짜", value=st.session_state.init_date, key="date_input")
        tm = c_time.time_input("현지 시간", value=st.session_state.init_time, key="time_input")
    
    with col3:
        duration = st.number_input("녹화 시간(분)", min_value=1, value=60, key="dur_input")
        is_now = st.checkbox("🚀 즉시 실행", key="now_input")

    # [핵심 수정] 한국 시간 변환 미리보기 알고리즘
    try:
        local_dt = datetime.combine(date, tm)
        # 1. 입력된 시간을 선택한 타임존 시간으로 인식
        localized_dt = selected_tz.localize(local_dt)
        # 2. 그것을 한국 시간(KST)으로 변환
        kst_preview = localized_dt.astimezone(KST)
        
        st.code(f"💡 확인: 선택하신 현지 시간은 한국 시간(KST)으로 [ {kst_preview.strftime('%Y-%m-%d %H:%M')} ] 입니다.")
    except Exception as e:
        st.caption(f"시간 변환 대기 중... ({e})")

    if st.button("✅ 예약 확정하기", use_container_width=True, type="primary"):
        if web_url:
            try:
                # DB에는 전 세계 공통 기준인 UTC로 저장합니다.
                utc_dt = localized_dt.astimezone(pytz.utc).isoformat()
                status = "trigger" if is_now else "pending"
                
                supabase.table("webinar_reservations").insert({
                    "webinar_url": web_url,
                    "scheduled_at": utc_dt,
                    "duration_min": duration,
                    "status": status
                }).execute()
                
                st.success(f"🎉 예약 성공! 한국 시간 {kst_preview.strftime('%H:%M')}에 시작됩니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 저장 실패: {e}")
        else:
            st.warning("URL을 입력해 주세요.")

# [Section 4: 실시간 현황 모니터링 - 에러 수정 버전]
st.divider()
st.subheader("📋 실시간 예약 현황")

try:
    # 최신 예약 10건 조회
    response = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(10).execute()
    
    # [수정 포인트] response.data가 존재하면 사용, 없으면 response 자체를 리스트로 취급
    items = getattr(response, 'data', response)
    
    if items:
        for item in items:
            with st.container(border=True):
                m1, m2, m3 = st.columns([3, 1, 1])
                with m1:
                    st.write(f"🔗 {item.get('webinar_url', 'URL 없음')}")
                    # 시간 표시 로직 (Z 제거 및 한국 시간 변환)
                    raw_ts = item.get('scheduled_at', '')
                    if raw_ts:
                        u_dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                        k_dt = u_dt.astimezone(KST)
                        st.caption(f"예약시간(KST): {k_dt.strftime('%Y-%m-%d %H:%M')} | {item.get('duration_min', 0)}분")
                
                with m2:
                    st_val = item.get('status', 'unknown')
                    if st_val == "pending": st.info("📅 대기 중")
                    elif st_val == "running": st.warning("⏳ 녹화 중")
                    elif st_val == "completed": st.success("✅ 완료됨")
                    elif st_val == "trigger": st.error("🚀 서버 응답 대기")
                    else: st.write(f"❓ {st_val}")
                
                with m3:
                    # 삭제 버튼
                    if st.button("취소/삭제", key=f"del_db_{item.get('id')}"):
                        supabase.table("webinar_reservations").delete().eq("id", item.get('id')).execute()
                        st.rerun()
    else:
        st.caption("대기 중인 예약이 없습니다.")
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")