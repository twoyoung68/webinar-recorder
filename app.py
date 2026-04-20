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
            info = json.loads(firebase_json, strict=False)
            cred = credentials.Certificate(info)
        except Exception as e:
            st.error(f"⚠️ Firebase 설정 오류: JSON 형식을 확인하세요. ({e})")
            st.stop()
    else:
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
st.info("해외 현지 시간을 입력하면 시스템이 자동으로 한국 시간(KST) 및 서버 시간(UTC)으로 변환합니다.")

# [Section 3: 현지 시간 기반 예약]

    # [app.py - Section 3 수정본]
st.divider()
with st.container(border=True):
    st.subheader("📅 새 녹화 작업 예약")
    
    # [추가] 빨간색 안내 문구 (사용자 주의사항)
    st.markdown("""
        <div style="background-color: #ffebee; padding: 10px; border-radius: 5px; border: 1px solid #f44336;">
            <p style="color: #d32f2f; margin: 0; font-weight: bold; font-size: 1.1em;">
                ⚠️ 필독: 시스템 순찰 주기(10분)로 인해, 실제 세미나 시작 시간보다 
                <span style="text-decoration: underline;"> 5분 정도 앞당겨서 예약</span>해 주세요!
            </p>
            <p style="color: #d32f2f; margin: 5px 0 0 0; font-size: 0.9em;">
                (예: 3:00 세미나 시작 → 2:45~2:50으로 예약 권장)
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("") # 간격 조절
    
    

    web_url = st.text_input("웨비나 접속 URL", placeholder="https://...", key="url_input_unique")
    
    col1, col2, col3 = st.columns([1.5, 2, 1])
    
    with col1:
        tz_choice = st.selectbox("🌍 현지 타임존 선택", list(TIMEZONES.keys()), key="tz_select")
        selected_tz = pytz.timezone(TIMEZONES[tz_choice]) 
    
    with col2:
        now_local = datetime.now(selected_tz)
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

    try:
        local_dt_naive = datetime.combine(date, tm)
        localized_dt = selected_tz.localize(local_dt_naive)
        kst_preview = localized_dt.astimezone(KST)
        utc_dt_for_db = localized_dt.astimezone(pytz.utc)
        
        st.code(f"💡 확인: 선택하신 현지 시간은 한국 시간(KST)으로 [ {kst_preview.strftime('%Y-%m-%d %H:%M')} ] 입니다.")
    except Exception:
        pass

    if st.button("✅ 예약 확정하기", use_container_width=True, type="primary"):
        if web_url:
            try:
                utc_dt_str = utc_dt_for_db.isoformat()
                status = "trigger" if is_now else "pending"
                supabase.table("webinar_reservations").insert({
                    "webinar_url": web_url, "scheduled_at": utc_dt_str,
                    "duration_min": duration, "status": status
                }).execute()
                st.success(f"🎉 예약 성공! 한국 시간 {kst_preview.strftime('%H:%M')}에 시작됩니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 저장 실패: {e}")
        else:
            st.warning("URL을 입력해 주세요.")

# [Section 4: 실시간 현황 모니터링]
st.divider()
st.subheader("📋 실시간 녹화 및 예약 현황")

# 새로고침 버튼을 상단에 배치하여 사용자가 수동으로 상태를 갱신할 수 있게 합니다.
if st.button("🔄 현황 새로고침", use_container_width=True):
    st.rerun()

try:
    # 최신 예약 10개를 가져와서 예약 시간순으로 정렬
    response = supabase.table("webinar_reservations") \
        .select("*") \
        .order("scheduled_at", desc=True) \
        .limit(10) \
        .execute()
    
    items = getattr(response, 'data', response)
    
    if items:
        for item in items:
            # 개별 항목을 테두리가 있는 박스(container)로 감싸 가독성을 높임
            with st.container(border=True):
                m1, m2, m3 = st.columns([3, 1, 1])
                
                with m1:
                    # URL 표시
                    st.write(f"🔗 **{item.get('webinar_url')}**")
                    
                    # 시간 변환 (UTC -> KST)
                    raw_ts = item.get('scheduled_at', '')
                    if raw_ts:
                        # ISO 포맷의 Z(UTC)를 파이썬 타임존 객체로 변환
                        u_dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
                        k_dt = u_dt.astimezone(KST)
                        st.caption(f"⏰ 시작 시간(KST): {k_dt.strftime('%Y-%m-%d %H:%M')} | ⏳ 녹화 분량: {item.get('duration_min')}분")
                
                with m2:
                    st_val = item.get('status')
                    # 상태별 시각적 피드백 (배지 및 색상 활용)
                    if st_val == "pending":
                        st.info("📅 예약 대기 중")
                    elif st_val == "running":
                        st.warning("⚡ 실시간 녹화 중") # 주황색으로 강조되어 눈에 잘 띔
                    elif st_val == "completed":
                        st.success("✅ 녹화 완료")
                    elif st_val == "trigger":
                        st.error("🚀 엔진 가동 중...") # 즉시 실행 버튼 클릭 후 서버 응답 대기 상태
                    elif st_val == "failed" or st_val == "error":
                        st.error("❌ 오류 발생")
                    else:
                        st.write(f"❓ {st_val}")
                
                with m3:
                    # 삭제 버튼 (데이터베이스에서 해당 예약 삭제)
                    if st.button("🗑️ 삭제", key=f"del_db_{item.get('id')}", use_container_width=True):
                        supabase.table("webinar_reservations").delete().eq("id", item.get('id')).execute()
                        st.toast(f"ID {item.get('id')} 작업이 삭제되었습니다.")
                        st.rerun()
    else:
        st.info("현재 등록된 예약 내역이 없습니다. 상단에서 새로운 녹화를 예약해 보세요.")

except Exception as e:
    st.error(f"데이터베이스 로드 중 오류가 발생했습니다: {e}")

# [Section 5: 사이드바 복구 (비밀번호 제거)]
st.sidebar.title("⚙️ 서버 시스템 관리")
st.sidebar.subheader("🗑️ 서버 영상 파일 관리")

try:
    blobs = list(bucket.list_blobs())
    used_mb = sum([b.size for b in blobs]) / (1024 * 1024)
    st.sidebar.write(f"📊 스토리지 사용량: **{used_mb:.1f} / 5120 MB**")
    
    if not blobs:
        st.sidebar.caption("저장된 파일이 없습니다.")
    else:
        for b in blobs:
            with st.sidebar.container():
                c_s1, c_s2 = st.columns([3, 1])
                c_s1.caption(f"📄 {b.name}")
                if c_s2.button("삭제", key=f"side_file_{b.name}"):
                    b.delete()
                    st.rerun()
except Exception as e:
    st.sidebar.error(f"파일 목록 로드 실패: {e}")

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