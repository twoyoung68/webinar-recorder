import streamlit as st
import os
import pandas as pd
from supabase import create_client
from datetime import datetime
import pytz

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# [요청사항 반영] 관리자 마스터 비밀번호
MASTER_PASSWORD = os.getenv("ADMIN_PW", "1207") 

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

# --- 2. CSS 스타일: 디자인 일관성 유지 ---
st.markdown("""
    <style>
    .sidebar-main-title { color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; }
    div[data-testid="stRadio"] label p { font-size: 30px !important; font-weight: 800 !important; color: #004a99 !important; }
    .menu-focus-box { font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: #FFF5F2; margin-top: 20px; }
    .sidebar-divider { border-top: 2px solid #ddd; margin: 15px 0; }
    .time-box { background-color: #f0f4ff; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 15px 0; }
    .time-label { font-weight: bold; color: #555; font-size: 14px; }
    .time-value { color: #004a99; font-weight: 900; font-size: 18px; }
    .confirm-time { color: #28a745; font-weight: 700; }
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
with st.sidebar.expander("🔐 관리자 모드 (비번: 1207)"):
    admin_input = st.text_input("마스터 비번", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 실시간 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약 입력")
        
        # 엔터키 오작동 방지를 위해 폼 외부에서 입력 받음
        webinar_title = st.text_input("1. 웨비나 명칭", placeholder="예: Hydrogen_Tech_Seminar")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            selected_zone = st.selectbox("3. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2:
            duration = st.number_input("4. 녹화 시간 (분)", min_value=1, value=60)
        with c3:
            del_pw = st.text_input("5. 삭제 비밀번호", type="password")
        
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        now_local = datetime.now(target_tz)
        
        col_d, col_t = st.columns(2)
        with col_d:
            l_date = st.date_input("6. 현지 시작 날짜", now_local.date())
        with col_t:
            # [오류 수정] 사용자가 선택한 시각이 즉시 변수에 반영되도록 설정
            l_time = st.time_input("7. 현지 시작 시각", now_local.time())

        # 사용자가 입력한 날짜와 시각을 결합하여 타임존 고정
        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        # [시간 변환 프리뷰]
        st.markdown(f"""
            <div class="time-box">
                <span class="time-label">🔍 예약 시간 확인 (한국 기준):</span><br>
                <span class="time-value">{kst_preview.strftime('%Y-%m-%d %H:%M')} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        # [요청사항 반영] 확인 체크박스 (절대 삭제하지 않음)
        confirm_check = st.checkbox("✅ 위 입력한 현지 시각과 정보가 정확함을 최종 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ '최종 확인' 체크박스를 먼저 선택해 주세요.")
            elif webinar_title and webinar_url and del_pw:
                # 미래 시간 검증
                if localized_dt < datetime.now(target_tz):
                    st.error("❌ 과거 시간으로는 예약할 수 없습니다.")
                else:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! 현지 시각 {l_time.strftime('%H:%M')}에 시작됩니다.")
                    st.rerun()
            else:
                st.error("⚠️ 누락 항목이 있습니다. 명칭, URL, 비밀번호를 모두 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (글로벌 현지 시간 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            # 시간 데이터 복원
            tz_name = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_name, 'Asia/Seoul'))
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            
            # [요청사항 반영] 예약 확정 시각 (DB의 created_at 활용)
            confirmed_at = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%m-%d %H:%M')
            
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            with st.expander(f"{status_icon} [현지시각: {sched_local.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.write(f"🔗 **URL:** {item['webinar_url']}")
                    st.markdown(f"""
                        <p>📍 <b>글로벌 시작 (현지):</b> {sched_local.strftime('%Y-%m-%d %H:%M')} ({tz_name})</p>
                        <p>📝 <b>예약 확정 일시 (KST):</b> <span class="confirm-time">{confirmed_at}</span></p>
                    """, unsafe_allow_html=True)
                with col_del:
                    if is_admin:
                        if st.button("🗑️ 삭제", key=f"adm_del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()
                    else:
                        pw_in = st.text_input("비번", type="password", key=f"pw_{item['id']}")
                        if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                            if pw_in == item.get('delete_password'):
                                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                                st.rerun()
                            else: st.error("❌ 비번 틀림")
    else:
        st.info("현재 대기 중인 예약이 없습니다.")

# --- 6. [메뉴 2] 녹화 영상 ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 파일 관리")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    if item.get('is_downloaded'):
                        st.markdown('<span style="background-color:#e8f5e9; color:#2e7d32; padding:5px 10px; border-radius:5px; font-weight:bold;">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span style="background-color:#fff3e0; color:#ef6c00; padding:5px 10px; border-radius:5px; font-weight:bold;">⏳ 수령 전</span>', unsafe_allow_html=True)
                with c2:
                    if st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                        supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                        st.rerun()
                with c3:
                    v_url = item.get('video_url')
                    if v_url:
                        st.markdown(f'<a href="{v_url}" download target="_blank"><button style="width:100%; background-color:#FF5733; color:white; padding:12px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">💾 파일 받기</button></a>', unsafe_allow_html=True)
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("완료된 영상이 없습니다.")