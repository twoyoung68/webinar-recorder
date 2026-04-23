import streamlit as st
import os
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# 관리자 마스터 비밀번호
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
    div[data-testid="stRadio"] label p { font-size: 30px !important; font-weight: 800 !important; color: #004a99 !important; }
    .menu-focus-box { font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: #FFF5F2; margin-top: 20px; }
    .sidebar-divider { border-top: 2px solid #ddd; margin: 15px 0; }
    .global-time-highlight { color: #004a99; font-weight: 900; font-size: 20px; }
    .download-status { background-color: #e8f5e9; color: #2e7d32; padding: 5px 10px; border-radius: 5px; font-weight: bold; }
    .not-downloaded { background-color: #fff3e0; color: #ef6c00; padding: 5px 10px; border-radius: 5px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase = init_connection()

# --- 4. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("마스터 비번", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)
st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 실시간 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 예약 (모든 항목 입력 필수)")
        # clear_on_submit=False로 설정하여 입력값 유지
        with st.form("recording_form", clear_on_submit=False):
            webinar_title = st.text_input("웨비나 명칭", placeholder="예: Hydrogen_Seminar_2026")
            webinar_url = st.text_input("웨비나 접속 URL")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                selected_zone_name = st.selectbox("개최지 타임존", list(WORLD_ZONES.keys()))
            with c2:
                duration = st.number_input("녹화 시간 (분)", min_value=1, value=60)
            with c3:
                del_pw = st.text_input("삭제 비밀번호 (4자리 이상)", type="password")
            
            target_tz = pytz.timezone(WORLD_ZONES[selected_zone_name])
            now_local = datetime.now(target_tz)
            
            col_d, col_t = st.columns(2)
            with col_d:
                local_date = st.date_input("현지 시작 날짜", now_local.date())
            with col_t:
                local_time = st.time_input("현지 시작 시각", now_local.time())

            st.info("💡 웨비나 명칭, URL, 비밀번호를 모두 입력해야 예약이 확정됩니다.")
            submit = st.form_submit_button("🚀 예약 확정 (Schedule Now)")
            
            if submit:
                if webinar_title and webinar_url and del_pw:
                    localized_dt = target_tz.localize(datetime.combine(local_date, local_time))
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone_name,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! 현지 시각 {local_time.strftime('%H:%M')}에 녹화가 시작됩니다.")
                    st.rerun()
                else:
                    st.error("⚠️ 누락된 항목이 있습니다. 명칭, URL, 비밀번호를 모두 확인해 주세요.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (글로벌 현지 시간 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            # DB에서 가져온 시간을 현지 타임존으로 변환
            tz_name = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_name, 'Asia/Seoul'))
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            # [요청사항] 제목에 현지 시작 시각만 표시
            with st.expander(f"{status_icon} [현지시각: {sched_local.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"🔗 **접속 URL:** {item['webinar_url']}")
                    st.markdown(f"📍 **현지 녹화 시작:** <span class='global-time-highlight'>{sched_local.strftime('%Y-%m-%d %H:%M')} ({tz_name})</span>", unsafe_allow_html=True)
                with col_b:
                    if is_admin:
                        if st.button("🗑️ 즉시 삭제", key=f"adm_del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()
                    else:
                        pw_input = st.text_input("삭제 비번", type="password", key=f"pw_{item['id']}")
                        if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                            if pw_input == item.get('delete_password'):
                                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                                st.rerun()
                            else: st.error("❌ 비번 틀림")

# --- 6. [메뉴 2] 녹화 영상 ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 및 다운로드 관리")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    # [요청사항] 다운로드 여부를 여기서만 표시
                    if item.get('is_downloaded'):
                        st.markdown('<span class="download-status">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span class="not-downloaded">⏳ 미확인 (파일 수령 전)</span>', unsafe_allow_html=True)
                
                with c2:
                    video_url = item.get('video_url')
                    if video_url:
                        # 다운로드 버튼 클릭 시 상태 업데이트를 위한 가이드 버튼
                        if st.button("📥 수령 확인", key=f"chk_{item['id']}", help="파일을 받으셨다면 클릭해 주세요."):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                
                with c3:
                    if video_url:
                        st.markdown(f'<a href="{video_url}" download target="_blank"><button style="width:100%; background-color:#FF5733; color:white; padding:12px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">💾 파일 받기</button></a>', unsafe_allow_html=True)
                
                if is_admin:
                    if st.button("🗑️ 관리자 영구 삭제", key=f"adm_f_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else: st.info("아직 완료된 영상이 없습니다.")