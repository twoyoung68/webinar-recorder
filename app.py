import streamlit as st
import os
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# 관리자 마스터 비밀번호 (보안을 위해 환경변수 권장, 기본값 ti1234)
MASTER_PASSWORD = os.getenv("ADMIN_PW", "ti1234") 

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore"
}

# --- 2. CSS 스타일: 디자인 및 시인성 강화 ---
st.markdown("""
    <style>
    .sidebar-main-title { color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; line-height: 1.2; }
    div[data-testid="stRadio"] label p { font-size: 28px !important; font-weight: 800 !important; color: #004a99 !important; }
    .menu-focus-box { font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: #FFF5F2; margin-top: 20px; }
    .sidebar-divider { border-top: 2px solid #ddd; margin: 15px 0; }
    .kst-preview-box { background-color: #eef2ff; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 10px 0; }
    .download-badge { background-color: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .pending-badge { background-color: #fff3e0; color: #ef6c00; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
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

# 관리자 인증 섹션
st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
with st.sidebar.expander("🔐 관리자 모드"):
    admin_input = st.text_input("마스터 비번 입력", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)
    if is_admin:
        st.sidebar.success("👑 관리자 권한 활성화")

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)
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
            
            col1, col2, col3 = st.columns(3)
            with col1:
                selected_zone_name = st.selectbox("개최지 타임존", list(WORLD_ZONES.keys()))
            with col2:
                duration = st.number_input("녹화 시간 (분)", min_value=1, value=60)
            with col3:
                del_pw = st.text_input("삭제 비밀번호", type="password", help="예약 삭제 시 본인 확인용")
            
            target_tz = pytz.timezone(WORLD_ZONES[selected_zone_name])
            now_local = datetime.now(target_tz)
            
            col_d, col_t = st.columns(2)
            with col_d:
                local_date = st.date_input("현지 시작 날짜", now_local.date())
            with col_t:
                # [Error Fix] now_at_local -> now_local로 오타 수정
                local_time = st.time_input("현지 시작 시각", now_local.time())

            # 한국 시각 변환 프리뷰
            localized_dt = target_tz.localize(datetime.combine(local_date, local_time))
            kst_dt = localized_dt.astimezone(KST)
            st.markdown(f"""<div class="kst-preview-box">🇰🇷 <b>한국 시작 시각: {kst_dt.strftime('%Y-%m-%d %H:%M')} (KST)</b></div>""", unsafe_allow_html=True)

            st.markdown("---")
            confirm_check = st.checkbox("✅ 입력한 정보와 한국 시작 시각이 정확함을 확인했습니다.")
            
            # [Error Fix] st.form_submit_button은 반드시 st.form 블록 내부에 존재해야 함
            submit = st.form_submit_button("🚀 예약 확정 (Schedule Now)")
            
            if submit:
                if not confirm_check:
                    st.warning("⚠️ 확인 체크박스를 먼저 선택해 주세요.")
                elif webinar_title and webinar_url and del_pw:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone_name,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! (KST: {kst_dt.strftime('%H:%M')})")
                    st.rerun()
                else:
                    st.warning("⚠️ 모든 정보를 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            sched_dt = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            req_dt = pd.to_datetime(item['created_at']).astimezone(KST)
            status_tag = '✅ 다운로드됨' if item.get('is_downloaded') else '⏳ 미확인'
            
            with st.expander(f"[{item['status'].upper()}] {item['title']} | 시작: {sched_dt.strftime('%m-%d %H:%M')}"):
                st.write(f"상태: **{status_tag}**")
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"🔗 URL: {item['webinar_url']}")
                    st.write(f"🇰🇷 한국 시각: {sched_dt.strftime('%Y-%m-%d %H:%M')}")
                    st.write(f"📝 신청 시각: {req_dt.strftime('%Y-%m-%d %H:%M')}")
                with col_b:
                    if is_admin:
                        if st.button("🗑️ 관리자 삭제", key=f"adm_del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()
                    else:
                        pw_input = st.text_input("비번 입력", type="password", key=f"pw_{item['id']}")
                        if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                            if pw_input == item.get('delete_password'):
                                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                                st.rerun()
                            else: st.error("❌ 비번 틀림")

# --- 6. [메뉴 2] 녹화 영상 ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 영상 확인")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    kst_finish = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
                    st.write(f"📅 완료(KST): {kst_finish}")
                    if item.get('is_downloaded'): st.markdown('<span class="download-badge">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                
                with c2:
                    if st.button("📥 수령 확인", key=f"check_{item['id']}"):
                        supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                        st.rerun()
                
                with c3:
                    video_url = item.get('video_url')
                    if video_url:
                        st.markdown(f'<a href="{video_url}" download target="_blank"><button style="width:100%; background-color:#FF5733; color:white; padding:12px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">💾 다운로드</button></a>', unsafe_allow_html=True)
                
                if is_admin:
                    if st.button("🗑️ 항목 영구 삭제 (관리자)", key=f"adm_f_del_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else: st.info("완료된 영상이 없습니다.")