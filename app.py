import streamlit as st
import os
import pandas as pd
import requests
import pytz
from supabase import create_client
from datetime import datetime

# --- 1. 페이지 및 환경 설정 ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')
MASTER_PASSWORD = "1207" # 지침: 내부 고정

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

# --- 2. 테마별 컬러 및 가독성 설정 ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)

if dark_mode:
    bg_color, main_text, sub_text = "#0e1117", "#FFFFFF", "#B0B0B0"
    preview_bg, preview_border = "#1e293b", "#3b82f6"
    sidebar_title, box_focus = "#4dabff", "#2d3748"
else:
    bg_color, main_text, sub_text = "#FFFFFF", "#1A1A1A", "#555555"
    preview_bg, preview_border = "#F0F7FF", "#004a99"
    sidebar_title, box_focus = "#000080", "#FFF5F2"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {main_text}; }}
    .sidebar-main-title {{ color: {sidebar_title} !important; font-size: 24px !important; font-weight: 800 !important; }}
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: {sidebar_title} !important; }}
    .menu-focus-box {{ 
        font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; 
        text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; 
        background-color: {box_focus}; margin-top: 20px; 
    }}
    .sidebar-divider {{ border-top: 2px solid #ddd; margin: 15px 0; }}
    .time-preview-box {{ 
        background-color: {preview_bg}; padding: 18px; border-radius: 12px; 
        border: 2px solid {preview_border}; margin: 15px 0; 
    }}
    .preview-kst {{ color: #FF5733; font-weight: 900; font-size: 24px; }}
    .confirm-tag {{ color: #28a745; font-weight: 800; font-size: 15px; }}
    .global-val {{ color: {preview_border}; font-weight: 800; font-size: 18px; }}
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
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)

if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="border-color:#004a99; color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약 입력")
        webinar_title = st.text_input("1. 웨비나 명칭", placeholder="명칭 입력 후 엔터를 쳐도 체크박스가 없으면 예약되지 않습니다.")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        c_mail, c_pw = st.columns(2)
        with c_mail:
            user_email = st.text_input("3. 확인용 이메일 주소", placeholder="기입력된 메일과 일치 여부 확인용")
        with c_pw:
            del_pw = st.text_input("4. 삭제 비밀번호", type="password")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("6. 녹화 시간 (분)", min_value=1, value=60)
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        with col_d: l_date = st.date_input("7. 현지 시작 날짜", datetime.now(target_tz).date())
        with col_t: l_time = st.time_input("8. 현지 시작 시각", value=datetime.now(target_tz).time(), key="main_time_input")

        # 시간 로직
        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-preview-box">
                <span style="color: {sub_text}; font-size: 15px;">🔍 <b>예약 시각 최종 확인 (한국 기준):</b></span><br>
                <span class="preview-kst">{kst_preview.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        confirm_check = st.checkbox("✅ 위 정보와 한국 시작 시각이 정확함을 최종 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
            elif webinar_title and webinar_url and del_pw:
                if localized_dt < datetime.now(target_tz):
                    st.error("❌ 과거 시각으로는 예약할 수 없습니다.")
                else:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url, "email": user_email,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success("✅ 예약 완료!")
                    st.rerun()
            else:
                st.error("⚠️ 누락 항목이 있습니다.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (현지 시작 시각 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            tz_n = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_n, 'Asia/Seoul'))
            # [오류 해결] 변수명을 sched_local로 통일
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            conf_kst = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%m-%d %H:%M')
            
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            with st.expander(f"{status_icon} [현지: {sched_local.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.write(f"🔗 **URL:** {item['webinar_url']}")
                    # [오류 해결] 변수명 sched_local 사용
                    st.markdown(f"📍 **글로벌 시작:** <span class='global-val'>{sched_local.strftime('%Y-%m-%d %H:%M')} ({tz_n})</span>", unsafe_allow_html=True)
                    st.markdown(f'<p class="confirm-tag">📝 예약 확정 일시: {conf_kst} (KST)</p>', unsafe_allow_html=True)
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
                            else: st.error("비번 틀림")

# --- 6. [메뉴 2] 녹화 영상 ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 파일 관리")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    if item.get('is_downloaded'):
                        st.markdown('<span style="background-color:#e8f5e9; color:#2e7d32; padding:5px 10px; border-radius:5px; font-weight:800;">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span style="background-color:#fff3e0; color:#ef6c00; padding:5px 10px; border-radius:5px; font-weight:800;">⏳ 수령 전</span>', unsafe_allow_html=True)
                with c2:
                    if st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                        supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                        st.rerun()
                with c3:
                    v_url = item.get('video_url')
                    if v_url:
                        try:
                            response = requests.get(v_url)
                            st.download_button(
                                label="💾 노트북 저장",
                                data=response.content,
                                file_name=f"{item['title']}.webm",
                                mime="video/webm",
                                key=f"dl_{item['id']}",
                                use_container_width=True
                            )
                        except: st.error("파일 로드 실패")
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else: st.info("완료된 영상이 없습니다.")