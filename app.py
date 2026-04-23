import streamlit as st
import os
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# [요청사항] 관리자 마스터 비밀번호 설정
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

# --- 2. CSS 스타일: 디자인 및 가시성 강화 ---
st.markdown("""
    <style>
    /* 사이드바 제목: 군청색 & 볼드체 */
    .sidebar-main-title {
        color: #000080 !important;
        font-size: 24px !important;
        font-weight: 800 !important;
        line-height: 1.2;
    }
    /* 메뉴 라벨 3배 확대 */
    div[data-testid="stRadio"] label p {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #004a99 !important;
    }
    /* 선택 메뉴 강조 박스 */
    .menu-focus-box {
        font-size: 38px !important;
        font-weight: 900 !important;
        color: #FF5733 !important;
        text-align: center;
        border: 4px solid #FF5733;
        border-radius: 20px;
        padding: 15px;
        background-color: #FFF5F2;
        margin-top: 20px;
    }
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
    admin_input = st.text_input("마스터 비번 (1207)", type="password")
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
    st.title("📅 글로벌 웨비나 예약 시스템")
    
    with st.container(border=True):
        st.subheader("📝 신규 예약 입력 (모든 항목 입력 필수)")
        
        # [엔터키 전송 방지] 폼(form) 대신 일반 위젯을 사용하여 실시간 프리뷰를 제공하고 실수를 막습니다.
        webinar_title = st.text_input("1. 웨비나 명칭", placeholder="예: Hydrogen_Seminar_2026")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_zone = st.selectbox("3. 개최지 타임존", list(WORLD_ZONES.keys()))
        with col2:
            duration = st.number_input("4. 녹화 시간 (분)", min_value=1, value=60)
        with col3:
            del_pw = st.text_input("5. 삭제 비밀번호", type="password", help="본인 예약 취소 시 필요")
        
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        now_at_local = datetime.now(target_tz)
        
        col_d, col_t = st.columns(2)
        with col_d:
            l_date = st.date_input("6. 현지 시작 날짜", now_at_local.date())
        with col_t:
            # 사용자가 입력한 시간을 정확히 받기 위해 수동 입력을 지원하는 time_input 사용
            l_time = st.time_input("7. 현지 시작 시각 (미래 시각 입력)", now_at_local.time())

        # [글로벌 시각 동기화 검증] 사용자가 입력한 값을 즉시 변환하여 보여줌
        # naive 객체를 생성한 뒤 선택한 타임존으로 고정(localize)합니다.
        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        st.markdown(f"""
            <div style="background-color: #f0f4ff; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 20px 0;">
                <span style="font-size: 16px; color: #555;">🔍 <b>예약 시간 최종 확인 (한국 기준):</b></span><br>
                <span style="font-size: 22px; color: #004a99; font-weight: 900;">
                    {kst_preview.strftime('%Y-%m-%d %H:%M')} (KST)
                </span><br>
                <span style="font-size: 14px; color: #777;">※ 위 시각에 서버에서 녹화가 시작됩니다.</span>
            </div>
        """, unsafe_allow_html=True)

        # [요청사항 반영] 확인 체크박스 (이것이 체크되어야만 버튼이 작동함)
        st.markdown("---")
        confirm_check = st.checkbox("✅ 입력한 웨비나 명칭, URL, 현지 시각이 정확함을 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ '최종 확인' 체크박스를 먼저 선택해 주세요.")
            elif webinar_title and webinar_url and del_pw:
                # 미래 시각인지 최종 검증 (현재 시점보다 이후여야 함)
                if localized_dt < datetime.now(target_tz):
                    st.error("❌ 현재보다 이전 시간으로는 예약할 수 없습니다. 시각을 다시 확인해 주세요.")
                else:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! 현지 시각 {l_time.strftime('%H:%M')}에 작동합니다.")
                    st.rerun()
            else:
                st.error("⚠️ 누락 항목: 명칭, URL, 비밀번호를 모두 입력해야 예약이 가능합니다.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 현황 (현지 시작 시각 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            tz_name = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_name, 'Asia/Seoul'))
            # DB의 시간을 해당 국가의 현지 시간으로 변환
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            # [요청사항] 현지 시간만 큼직하게 표시
            with st.expander(f"{status_icon} [현지: {sched_local.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"🔗 **URL:** {item['webinar_url']}")
                    st.markdown(f"📍 **현지 시작:** <span class='global-time-highlight'>{sched_local.strftime('%Y-%m-%d %H:%M')} ({tz_name})</span>", unsafe_allow_html=True)
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
                            else: st.error("비번 틀림")

# --- 6. [메뉴 2] 녹화 영상 (다운로드 관리) ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 및 파일 관리")
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
                        st.markdown('<span class="not-downloaded">⏳ 미확인 (수령 전)</span>', unsafe_allow_html=True)
                
                with c2:
                    video_url = item.get('video_url')
                    if video_url:
                        # 사용자가 수동으로 체크하도록 하여 관리자에게 알림
                        if st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                            supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                            st.rerun()
                
                with c3:
                    if video_url:
                        st.markdown(f'<a href="{video_url}" download target="_blank"><button style="width:100%; background-color:#FF5733; color:white; padding:12px; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">💾 파일 받기</button></a>', unsafe_allow_html=True)
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else: st.info("아직 완료된 영상이 없습니다.")