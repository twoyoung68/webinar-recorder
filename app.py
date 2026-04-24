import streamlit as st
import os
import pandas as pd
import requests
from supabase import create_client
from datetime import datetime
import pytz

# --- 1. 페이지 및 환경 설정 (일관성 유지) ---
st.set_page_config(page_title="Plant TI Team Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# [지침] 마스터 비밀번호 내부 고정 (1207)
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

# --- 2. CSS 스타일: 대우건설 Plant TI 팀 표준 디자인 ---
st.markdown("""
    <style>
    .sidebar-main-title { color: #000080 !important; font-size: 24px !important; font-weight: 800 !important; }
    div[data-testid="stRadio"] label p { font-size: 30px !important; font-weight: 800 !important; color: #004a99 !important; }
    .menu-focus-box { font-size: 38px !important; font-weight: 900 !important; color: #FF5733 !important; text-align: center; border: 4px solid #FF5733; border-radius: 20px; padding: 15px; background-color: #FFF5F2; margin-top: 20px; }
    .sidebar-divider { border-top: 2px solid #ddd; margin: 15px 0; }
    .preview-box { background-color: #f0f4ff; padding: 15px; border-radius: 10px; border: 2px solid #004a99; margin: 15px 0; }
    .preview-kst { color: #004a99; font-weight: 900; font-size: 20px; }
    .confirm-tag { color: #28a745; font-weight: 700; font-size: 14px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 서비스 연결 ---
@st.cache_resource
def init_connection():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

supabase = init_connection()

# --- 4. 사이드바 구성 (디자인 일관성) ---
st.sidebar.markdown("## 🏗️ Daewoo E&C")
st.sidebar.markdown('<p class="sidebar-main-title">Plant TI Team<br>Webinar Recorder</p>', unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
with st.sidebar.expander("🔐 관리자 전용"):
    admin_input = st.text_input("Master Password", type="password")
    is_admin = (admin_input == MASTER_PASSWORD)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
menu = st.sidebar.radio("Menu Selection", ["📅 예약 및 현황", "🎥 녹화 영상"], index=0)

st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
if menu == "🎥 녹화 영상":
    st.sidebar.markdown('<div class="menu-focus-box">🎥<br>녹화<br>영상</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<div class="menu-focus-box" style="color:#004a99; border-color:#004a99; background-color:#F0F7FF;">📅<br>예약<br>현황</div>', unsafe_allow_html=True)

# --- 5. [메뉴 1] 예약 및 현황 (시간 로직 및 안전장치 유지) ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 웨비나 예약 및 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 녹화 예약 입력")
        
        webinar_title = st.text_input("1. 웨비나 명칭", placeholder="입력 후 엔터를 쳐도 체크박스가 없으면 예약되지 않습니다.")
        webinar_url = st.text_input("2. 웨비나 접속 URL")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            selected_zone = st.selectbox("3. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2:
            duration = st.number_input("4. 녹화 시간 (분)", min_value=1, value=60)
        with c3:
            del_pw = st.text_input("5. 삭제 비밀번호", type="password")
            
        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        col_d, col_t = st.columns(2)
        with col_d:
            l_date = st.date_input("6. 현지 시작 날짜", datetime.now(target_tz).date())
        with col_t:
            l_time = st.time_input("7. 현지 시작 시각", value=datetime.now(target_tz).time(), key="time_input_widget")

        # 현지 시각 반영 및 한국 시각 변환 (일관성 유지)
        localized_dt = target_tz.localize(datetime.combine(l_date, l_time))
        kst_preview = localized_dt.astimezone(KST)
        
        st.markdown(f"""
            <div class="preview-box">
                <span style="font-size: 15px; color: #555;">🔍 <b>예약 시각 최종 확인 (한국 기준):</b></span><br>
                <span class="preview-kst">{kst_preview.strftime('%Y-%m-%d %H:%M')} (KST)</span>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        # [지침] 확인 체크박스 (절대 유지)
        confirm_check = st.checkbox("✅ 위 정보와 한국 시작 시각이 정확함을 최종 확인했습니다.")
        
        if st.button("🚀 예약 확정 (Schedule Now)", use_container_width=True):
            if not confirm_check:
                st.warning("⚠️ 반드시 '최종 확인' 체크박스를 선택해야 예약이 완료됩니다.")
            elif webinar_title and webinar_url and del_pw:
                if localized_dt < datetime.now(target_tz):
                    st.error("❌ 과거 시각으로는 예약할 수 없습니다.")
                else:
                    supabase.table("webinar_reservations").insert({
                        "title": webinar_title, "webinar_url": webinar_url,
                        "scheduled_at": localized_dt.isoformat(), "duration_min": duration,
                        "status": "pending", "timezone_name": selected_zone,
                        "delete_password": del_pw, "is_downloaded": False
                    }).execute()
                    st.success(f"✅ 예약 완료! {l_time.strftime('%H:%M')} (현지)에 녹화가 시작됩니다.")
                    st.rerun()
            else:
                st.error("⚠️ 누락 항목: 모든 정보를 입력해 주세요.")

    st.markdown("---")
    st.subheader("📋 실시간 예약 목록 (글로벌 현지 시간 기준)")
    res = supabase.table("webinar_reservations").select("*").order("scheduled_at", desc=False).execute()
    
    if res.data:
        for item in res.data:
            tz_name = item.get('timezone_name', '대한민국 (KST)')
            local_tz = pytz.timezone(WORLD_ZONES.get(tz_name, 'Asia/Seoul'))
            sched_local = pd.to_datetime(item['scheduled_at']).astimezone(local_tz)
            confirmed_kst = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%m-%d %H:%M')
            status_icon = "⏳" if item['status'] == "pending" else "⏺️" if item['status'] == "running" else "✅"
            
            with st.expander(f"{status_icon} [현지: {sched_local.strftime('%Y-%m-%d %H:%M')}] {item['title']}"):
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.write(f"🔗 **URL:** {item['webinar_url']}")
                    st.write(f"📍 **글로벌 시작:** {sched_local.strftime('%Y-%m-%d %H:%M')} ({tz_name})")
                    st.markdown(f'<p class="confirm-tag">📝 예약 확정 일시: {confirmed_kst} (KST)</p>', unsafe_allow_html=True)
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

# --- 6. [메뉴 2] 녹화 영상 (노트북 저장 오류 수정 버전) ---
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
                        st.markdown('<span style="background-color:#e8f5e9; color:#2e7d32; padding:5px 10px; border-radius:5px; font-weight:bold;">✅ 다운로드 완료</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span style="background-color:#fff3e0; color:#ef6c00; padding:5px 10px; border-radius:5px; font-weight:bold;">⏳ 수령 전</span>', unsafe_allow_html=True)
                
                with c2:
                    # [상태 업데이트 버튼]
                    if st.button("📥 수령 확인", key=f"chk_{item['id']}"):
                        supabase.table("webinar_reservations").update({"is_downloaded": True}).eq("id", item['id']).execute()
                        st.rerun()
                
                with c3:
                    video_url = item.get('video_url')
                    if video_url:
                        # [버그 수정] 브라우저 재생 에러 방지 및 노트북 직접 저장을 위해 st.download_button 사용
                        try:
                            # 1. 파일 데이터 가져오기
                            response = requests.get(video_url)
                            video_data = response.content
                            
                            # 2. 파일명 설정
                            file_ext = video_url.split('.')[-1] if '.' in video_url else 'webm'
                            download_filename = f"{item['title']}.{file_ext}"

                            # 3. 노트북 저장 버튼 생성
                            st.download_button(
                                label="💾 노트북 저장",
                                data=video_data,
                                file_name=download_filename,
                                mime=f"video/{file_ext}",
                                key=f"dl_{item['id']}",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error("⚠️ 파일 로드 실패")
                
                if is_admin:
                    if st.button("🗑️ 영구 삭제 (관리자)", key=f"adm_f_del_{item['id']}"):
                        supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                        st.rerun()
    else:
        st.info("완료된 영상이 없습니다.")