import streamlit as st
import os
import pandas as pd
from supabase import create_client
from datetime import datetime
import pytz

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# 관리자 마스터 비밀번호 (보안을 위해 환경변수 권장)
MASTER_PASSWORD = os.getenv("ADMIN_PW", "ti1234") 

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore"
}

# --- 2. CSS 스타일 ---
st.markdown("""
    <style>
    .sidebar-main-title { color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; }
    div[data-testid="stRadio"] label p { font-size: 28px !important; font-weight: 800 !important; color: #004a99 !important; }
    .download-badge { background-color: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; }
    .pending-badge { background-color: #fff3e0; color: #ef6c00; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase = init_connection()

# --- 4. 사이드바 (관리자 모드 추가) ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)

# 관리자 인증 섹션
st.sidebar.markdown("---")
with st.sidebar.expander("🔐 관리자 모드"):
    admin_input = st.text_input("마스터 비번 입력", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)
    if is_admin:
        st.sidebar.success("👑 관리자 권한 활성화")

st.sidebar.markdown("---")
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 예약 (삭제 비밀번호 필수)")
        with st.form("recording_form", clear_on_submit=True):
            webinar_title = st.text_input("웨비나 명칭")
            webinar_url = st.text_input("웨비나 접속 URL")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                selected_zone = st.selectbox("타임존", list(WORLD_ZONES.keys()))
            with c2:
                duration = st.number_input("녹화 시간(분)", min_value=1, value=60)
            with c3:
                # 삭제 비밀번호 입력칸 추가
                del_pw = st.text_input("삭제 비밀번호 (4자리 이상)", type="password", help="본인 예약 삭제 시 필요합니다.")
            
            target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
            now_local = datetime.now(target_tz)
            l_date = st.date_input("현지 날짜", now_local.date())
            l_time = st.time_input("현지 시각", now_at_local.time())

            st.markdown("---")
            if st.form_submit_button("🚀 예약 확정"):
                if not webinar_title or not webinar_url or not del_pw:
                    st.error("⚠️ 모든 정보(명칭, URL, 삭제 비밀번호)를 입력해 주세요.")
                else:
                    localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success("✅ 예약이 등록되었습니다!")
                    st.rerun()

    # 목록 표시 및 조건부 삭제
    st.markdown("---")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    if res.data:
        for item in res.data:
            sched_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST).strftime('%m-%d %H:%M')
            # 다운로드 상태 표시
            status_tag = '<span class="download-badge">✅ 다운로드됨</span>' if item.get('is_downloaded') else '<span class="pending-badge">⏳ 미확인</span>'
            
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {sched_kst}"):
                st.markdown(f"현황: {status_tag}", unsafe_allow_html=True)
                col_text, col_del = st.columns([4, 1])
                with col_text:
                    st.write(f"🔗 URL: {item['webinar_url']}")
                with col_del:
                    # 삭제 로직
                    if is_admin:
                        if st.button("🗑️ 즉시 삭제 (관리자)", key=f"adm_del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()
                    else:
                        pw_input = st.text_input("비번 입력 시 삭제 가능", type="password", key=f"pw_{item['id']}")
                        if st.button("🗑️ 삭제 요청", key=f"del_{item['id']}"):
                            if pw_input == item.get('delete_password'):
                                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                                st.rerun()
                            else:
                                st.error("❌ 비밀번호가 틀렸습니다.")

# --- 6. [메뉴 2] 녹화 영상 (다운로드 체크 기능 추가) ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 영상 리스트")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    if item.get('is_downloaded'):
                        st.markdown('<span class="download-badge">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="pending-badge">⏳ 미확인 (다운로드 전)</span>', unsafe_allow_html=True)
                
                with c2:
                    # 다운로드 버튼 클릭 시 상태 업데이트 로직
                    video_url = item.get('video_url')
                    if video_url:
                        if st.button("📥 다운로드 준비", key=f"ready_{item['id']}"):
                            # DB 업데이트: 다운로드 됨으로 표시
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                
                with c3:
                    # 실제 다운로드 링크는 준비 버튼을 누르거나 관리자일 때 활성화 (또는 항상 노출하되 기록만 남김)
                    if item.get('video_url'):
                        st.markdown(f'<a href="{item["video_url"]}" download target="_blank"><button style="width:100%; background-color:#FF5733; color:white; padding:12px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">💾 파일 받기</button></a>', unsafe_allow_html=True)
                
                # 관리자 전용 삭제 버튼 (영상 페이지에서도 관리 가능)
                if is_admin:
                    if st.button("🗑️ 이 항목 영구 삭제 (관리자 전용)", key=f"adm_file_del_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("완료된 영상이 없습니다.")