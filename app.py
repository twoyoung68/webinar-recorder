# [Section 1: Firebase 초기화 최종 안정화 버전]
import streamlit as st
import firebase_admin
from firebase_admin import credentials, storage
from supabase import create_client
import os
import json
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    
    if firebase_json:
        # 클라우드 환경: Secrets에서 읽기
        try:
            # 문자열 내의 줄바꿈이나 특수문자 문제를 방지하기 위해 정제 후 로드
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
        except Exception as e:
            st.error(f"⚠️ Firebase 설정 오류: JSON 형식을 확인하세요. ({e})")
            st.stop() # 에러 발생 시 진행 중단
    else:
        # 로컬 환경: 파일에서 읽기
        if os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
        else:
            st.error("❌ Firebase 키 파일이 없습니다.")
            st.stop()

    firebase_admin.initialize_app(cred, {
        'storageBucket': 'webinar-recorder.firebasestorage.app'
    })

bucket = storage.bucket()
KST = pytz.timezone('Asia/Seoul')


# 타임존 리스트
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
st.info("해외 현지 시간을 입력하면 시스템이 자동으로 서버 시간(UTC)으로 변환합니다.")

# [Section 3: 현지 시간 기반 예약 및 상태 유지]
st.divider()
with st.container(border=True):
    st.subheader("📅 새 녹화 작업 예약")
    
    # 중복 에러 방지를 위해 key는 단 한 번만 사용됨
    web_url = st.text_input("웨비나 접속 URL", placeholder="https://...", key="url_input_unique")
    
    col1, col2, col3 = st.columns([1.5, 2, 1])
    
    with col1:
        tz_choice = st.selectbox("🌍 현지 타임존 선택", list(TIMEZONES.keys()), key="tz_select")
        selected_tz = pytz.timezone("Asia/Seoul")
    
    with col2:
        # 현지 시간 입력을 위한 세션 스테이트 관리 (입력값 유지 로직)
        now_local = datetime.now(selected_tz)
        
        # 타임존이 바뀌었을 때만 초기 시간을 갱신
        if "prev_tz" not in st.session_state or st.session_state.prev_tz != tz_choice:
            st.session_state.init_date = now_local.date()
            st.session_state.init_time = now_local.time()
            st.session_state.prev_tz = tz_choice

        c_date, c_time = st.columns(2)
        # value에 세션 스테이트를 연결하여 사용자가 바꾼 값이 유지되게 함
        date = c_date.date_input("현지 날짜", value=st.session_state.init_date, key="date_input")
        tm = c_time.time_input("현지 시간", value=st.session_state.init_time, key="time_input")
    
    with col3:
        duration = st.number_input("녹화 시간(분)", min_value=1, value=60, key="dur_input")
        is_now = st.checkbox("🚀 즉시 실행", key="now_input")

    # 한국 시간 변환 미리보기
    try:
        local_dt = datetime.combine(date, tm)
        localized_dt = selected_tz.localize(local_dt)
        kst_preview = localized_dt.astimezone(KST)
        st.code(f"💡 확인: 선택하신 현지 시간은 한국 시간(KST)으로 [ {kst_preview.strftime('%Y-%m-%d %H:%M')} ] 입니다.")
    except Exception:
        pass

    if st.button("✅ 예약 확정하기", use_container_width=True, type="primary"):
        if web_url:
            try:
                utc_dt = localized_dt.astimezone(pytz.utc).isoformat()
                status = "trigger" if is_now else "pending"
                
                # pc_owner 없이 전송
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

# [Section 4: 실시간 현황 모니터링 수정본]
st.divider()
st.subheader("📋 실시간 예약 현황")

# st.button("🔄 현황 새로고침") # 수동 새로고침 버튼을 추가하면 확인이 더 빠릅니다.

try:
    # 캐시 방지를 위해 항상 최신 10개를 시간순으로 가져옴
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=True).limit(10).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                m1, m2, m3 = st.columns([3, 1, 1])
                with m1:
                    st.write(f"🔗 {item['webinar_url']}")
                    # 시간 표시 로직
                    u_dt = datetime.fromisoformat(item['scheduled_at'].replace('Z', '+00:00'))
                    k_dt = u_dt.astimezone(KST)
                    st.caption(f"예약시간(KST): {k_dt.strftime('%Y-%m-%d %H:%M')} | {item['duration_min']}분")
                
                with m2:
                    # 상태 표시 (DB의 실제 status 값을 그대로 반영)
                    st_val = item['status']
                    if st_val == "pending": 
                        st.info("📅 대기 중")
                    elif st_val == "running": 
                        st.warning("⏳ 녹화 중")
                    elif st_val == "completed": 
                        st.success("✅ 완료됨")
                    elif st_val == "trigger":
                        st.error("🚀 서버 응답 대기")
                    else:
                        st.write(f"❓ {st_val}")
                
                with m3:
                    if st.button("취소/삭제", key=f"del_db_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.caption("대기 중인 예약이 없습니다.")
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")

# [Section 5: 관리자 전용 제어 (비번 1207)]
st.sidebar.title("🔐 관리자 전용")
if st.sidebar.text_input("비밀번호", type="password") == "1207":
    st.sidebar.success("인증 완료")
    
    st.sidebar.subheader("🗑️ 서버 영상 파일 관리")
    blobs = list(bucket.list_blobs())
    used_mb = sum([b.size for b in blobs]) / (1024 * 1024)
    st.sidebar.write(f"📊 사용량: **{used_mb:.1f} / 5120 MB**")
    
    for b in blobs:
        c_s1, c_s2 = st.sidebar.columns([3, 1])
        c_s1.caption(b.name)
        if c_s2.button("삭제", key=f"side_file_{b.name}"):
            b.delete()
            st.rerun()

# [Section 6: 다운로드 센터]
st.divider()
st.subheader("📥 녹화 완료 영상 다운로드")
blobs = list(bucket.list_blobs())
if not blobs:
    st.info("아직 서버에 저장된 영상 파일이 없습니다.")
else:
    for blob in blobs:
        with st.container(border=True):
            d1, d2, d3 = st.columns([3, 1, 1])
            d1.write(f"📁 **{blob.name}**")
            d2.write(f"📏 {round(blob.size/(1024*1024), 1)} MB")
            d_url = blob.generate_signed_url(expiration=timedelta(hours=1))
            d3.link_button("💾 내 PC 저장", d_url, type="primary")