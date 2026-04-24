import streamlit as st
import os
import pandas as pd
import requests
import pytz
from supabase import create_client
from datetime import datetime

# --- 1. 페이지 및 환경 설정 (플랜트TI 표준) ---
st.set_page_config(
    page_title="Plant TI Team Webinar Recorder",
    page_icon="🎥",
    layout="wide",
)

KST = pytz.timezone('Asia/Seoul')
# [지침] 마스터 비밀번호 내부 고정 (UI 안내 절대 금지)
MASTER_PASSWORD = "1207" 

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

# --- 2. 다크 모드 및 디자인 설정 (디자인 가이드 준수) ---
dark_mode = st.sidebar.toggle("🌙 다크 모드 활성화", value=True)

if dark_mode:
    bg_color, text_color, box_color = "#0e1117", "#ffffff", "#1f2937"
    preview_bg = "#1e293b"
else:
    bg_color, text_color, box_color = "#ffffff", "#000000", "#FFF5F2"
    preview_bg = "#f0f4ff"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    /* 군청색 메인 타이틀 */
    .sidebar-main-title {{ color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; }}
    /* 메뉴 라벨 300% 확대 (지침 준수) */
    div[data-testid="stRadio"] label p {{ font-size: 30px !important; font-weight: 800 !important; color: #004a99 !important; }}
    /* 메뉴 하단 강조 박스 (오렌지색) */
    .menu-focus-box {{ font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: {box_color}; margin-top: 20px; }}
    .sidebar-divider {{ border-top: 2px solid #ddd; margin: 15px 0; }}
    /* 시간 확인 박스 */
    .time-preview-box {{ background-color: {preview_bg}; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 15px 0; }}
    .preview-kst {{ color: #004a99; font-weight: 900; font-size: 20px; }}
    .confirm-tag {{ color: #28a745; font-weight: 700; font-size: 14px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_connection()

# --- 4. 사이드바 구성 ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
with st.sidebar.expander("🔐 관리자 전용"):
    # 비번 안내 문구 제거 (사용자 지침)
    admin_input = st.text_input("Master Password", type="password")
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
    st.title("📅 글로벌 웨비나 예약 및 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약 입력")
        
        # [엔터키 전송 방지] 폼 대신 일반 위젯 사용
        webinar_title = st.text_input("1. 웨비나 명칭", placeholder="입력 후 엔터를 쳐도 체크박스가 없으면 예약되지 않습니다.")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        c_mail, c_pw = st.columns(2)
        with c_mail:
            # 봇이 현장에서 확인할 이메일 주소
            user_email = st.text_input("3. 확인용 이메일 주소", placeholder="기입력된 주소와 일치하는지 봇이 확인합니다.")
        with c_pw:
            del_pw = st.text_input("4. 삭제 비밀번호 (본인 확인용)", type="password")

        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("5. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("6. 녹화 시간 (분)", min_value=1, value=60)
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        with col_d: l_date = st.date_input("7. 현지 시작 날짜", datetime.now(target_tz).date())
        with col_t: l_time = st.time_input("8. 현지 시작 시각", value=datetime.now(target_tz).time(), key="time_input_master")

        # 글로벌 시각 변환 로직 (일관성 유지)
        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="time-preview-box">
                <span style="font-size: 15px; color: #888;">🔍 <b>예약 시각 최종 확인 (한국 기준):</b></span><br>
                <span class="preview-kst">{kst_preview.strftime("%Y-%m-%d %H:%M")} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        # [지침] 안전 체크박스 (절대 삭제 금지)
        confirm_check = st.checkbox("✅ 이메일 및 글로벌 시각 정보를 최종 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ 반드시 '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
            elif webinar_title and webinar_url and del_pw:
                # 과거 시간 예약 방지
                if localized_dt < datetime.now(target_tz):
                    st.error("❌ 과거 시각으로는 예약할 수 없습니다.")
                else:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url, "email": user_email,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! {l_time.strftime('%H:%M')} (현지)에 녹화가 시작됩니다.")
                    st.rerun()
            else:
                st.error("⚠️ 누락 항목: 모든 정보를 입력해 주세요.")

    # 목록 표시
    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (현지 시작 시각 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            tz_n = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_n, 'Asia/Seoul'))
            sched_l = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            # 신청(확정) 시각 정보 병기
            conf_kst = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%m-%d %H:%M')
            
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            with st.expander(f"{status_icon} [현지: {sched_l.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.write(f"🔗 **URL:** {item['webinar_url']}")
                    st.write(f"📍 **글로벌 시작:** {sched_l.strftime('%Y-%m-%d %H:%M')} ({tz_n})")
                    st.markdown(f'<p class="confirm-tag">📝 예약 확정 일시: {conf_kst} (KST)</p>', unsafe_allow_html=True)
                with col_del:
                    if is_admin:
                        if st.button("🗑️ 즉시 삭제", key=f"adm_del_{item['id']}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.rerun()
                    else:
                        pw_in = st.text_input("비번", type="password", key=f"pw_{item['id']}")
                        if st.button("🗑️ 삭제", key=f"del_{item['id']}"):
                            if pw_in == item.get('delete_password'):
                                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                                st.rerun()
                            else: st.error("비번 틀림")

# --- 6. [메뉴 2] 녹화 영상 (노트북 직접 저장 방식) ---
elif menu == "🎥 녹화 영상":
    st.title("🎥 녹화 완료 파일 관리")
    res = supabase.table("webinar_reservations").select("*").eq("status", "completed").order("created_at", desc=True).execute()
    
    if res.data:
        for item in res.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.subheader(f"📺 {item['title']}")
                    # 다운로드 상태 배지 (여기서만 표시)
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
                        # [버그 수정] 노트북 직접 저장을 위해 st.download_button 사용
                        try:
                            response = requests.get(v_url)
                            video_bytes = response.content
                            file_ext = v_url.split('.')[-1] if '.' in v_url else 'webm'
                            
                            st.download_button(
                                label="💾 노트북 저장",
                                data=video_bytes,
                                file_name=f"{item['title']}.{file_ext}",
                                mime=f"video/{file_ext}",
                                key=f"dl_btn_{item['id']}",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error("⚠️ 파일 로드 실패")
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_del_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("아직 완료된 영상이 없습니다.")