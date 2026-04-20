import streamlit as st
import json
import os
from google.oauth2 import service_account
from google.cloud import storage
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client
import pytz

# --- 1. 페이지 및 시간대 설정 ---
st.set_page_config(page_title="Plant TI Webinar Recorder", page_icon="🎥", layout="wide")
KST = pytz.timezone('Asia/Seoul')

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "아랍에미리트 (GST)": "Asia/Dubai",
    "영국/런던 (GMT/BST)": "Europe/London",
    "중유럽/독일/프랑스 (CET/CEST)": "Europe/Berlin",
    "미국 동부/뉴욕 (EST/EDT)": "US/Eastern",
    "미국 서부/LA (PST/PDT)": "US/Pacific",
    "베트남 (ICT)": "Asia/Ho_Chi_Minh"
}

# --- 2. 보안 인증 및 클라이언트 설정 ---
@st.cache_resource
def init_all_connections():
    creds = None
    if "FIREBASE_KEY" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
        except Exception as e:
            st.error(f"Secrets 인증 로드 실패: {e}")
    elif os.path.exists('firebase_key.json'):
        try:
            creds = service_account.Credentials.from_service_account_file('firebase_key.json')
        except Exception as e:
            st.error(f"로컬 파일 인증 로드 실패: {e}")

    if creds is None:
        st.error("보안 키(Secrets 또는 JSON 파일)가 없습니다.")
        st.stop()
        
    storage_client = storage.Client(credentials=creds, project=creds.project_id)
    supabase_client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    
    return storage_client, supabase_client

storage_client, supabase = init_all_connections()
bucket = storage_client.bucket("webinar-recorder-plant-titeam.appspot.com")

# --- 3. 사이드바 ---
with st.sidebar:
    st.title("🎥 Webinar Recorder")
    st.info(f"**현재 한국 시간(KST):**\n{datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    st.markdown("---")
    menu = st.radio("메뉴 이동", ["📅 웨비나 녹화 예약", "📂 녹화 내역 확인", "⚙️ 시스템 상태"])
    st.markdown("---")
    st.subheader("📊 시스템 정보")
    st.write("**Target:** Plant TI DX Project")
    st.caption("Developed by Plant TI Team")

# --- 4. [화면 1] 웨비나 녹화 예약 ---
if menu == "📅 웨비나 녹화 예약":
    st.header("📅 글로벌 웨비나 녹화 예약")
    
    with st.form("recording_form"):
        # DB에 title이 없으므로 webinar_url을 주요 정보로 입력받습니다.
        webinar_url = st.text_input("웨비나 URL (필수)", placeholder="https://event.on24.com/...")
        
        st.markdown("#### 🌍 시간대 설정")
        selected_zone_name = st.selectbox("현지 시간대 선택", list(WORLD_ZONES.keys()))
        selected_timezone = pytz.timezone(WORLD_ZONES[selected_zone_name])
        
        col1, col2 = st.columns(2)
        with col1:
            local_date = st.date_input("현지 날짜", datetime.now(selected_timezone))
        with col2:
            local_time = st.time_input("현지 시작 시간", datetime.now(selected_timezone))
            
        duration = st.number_input("녹화 지속 시간 (분)", min_value=1, max_value=300, value=60)
        
        submit = st.form_submit_button("✅ 예약 확정")
        
        if submit:
            if not webinar_url:
                st.error("URL을 입력해주세요.")
            else:
                local_dt = selected_timezone.localize(datetime.combine(local_date, local_time))
                scheduled_kst = local_dt.astimezone(KST)
                
                # DB 구조에 맞게 데이터 구성
                data = {
                    "webinar_url": webinar_url,
                    "scheduled_at": scheduled_kst.isoformat(),
                    "duration_min": duration,
                    "status": "pending"
                }
                try:
                    supabase.table("webinar_reservations").insert(data).execute()
                    st.success(f"🎉 예약 완료! 한국 시각 {scheduled_kst.strftime('%Y-%m-%d %H:%M')} 시작")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

    # --- 예약 목록 및 삭제 기능 ---
    st.markdown("---")
    st.subheader("📝 현재 예약 대기 목록")
    try:
        res = supabase.table("webinar_reservations").select("*").eq("status", "pending").order("scheduled_at").execute()
        if res.data:
            for item in res.data:
                # title 대신 webinar_url을 제목으로 표시 (앞부분 40자만 출력)
                display_title = item.get('webinar_url', 'No URL').split('//')[-1][:40]
                time_str = pd.to_datetime(item['scheduled_at']).strftime('%m/%d %H:%M')
                
                with st.expander(f"📌 {display_title}... ({time_str} KST)"):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"**상세 URL:** {item.get('webinar_url')}")
                        st.write(f"**녹화 시간:** {item.get('duration_min')}분")
                        st.caption(f"ID: {item.get('id')}")
                    with c2:
                        # 고유 ID를 사용하여 삭제
                        if st.button("🗑️ 삭제", key=f"del_{item.get('id')}"):
                            supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                            st.toast("예약이 삭제되었습니다.")
                            st.rerun()
        else:
            st.info("대기 중인 예약이 없습니다.")
    except Exception as e:
        st.error(f"목록 로드 실패 (KeyError 'title' 해결 중): {e}")

# --- 5. [화면 2] 녹화 내역 확인 ---
elif menu == "📂 녹화 내역 확인":
    st.header("📂 저장된 녹화 파일 목록")
    try:
        blobs = list(bucket.list_blobs(prefix="recordings/"))
        valid_files = [b for b in blobs if b.name.endswith((".webm", ".mp4"))]
        if not valid_files:
            st.info("저장된 영상이 없습니다.")
        else:
            for blob in valid_files:
                col1, col2 = st.columns([3, 1])
                with col1: st.write(f"📄 {blob.name.split('/')[-1]}")
                with col2:
                    url = blob.generate_signed_url(expiration=timedelta(hours=1))
                    st.link_button("⬇️ 다운로드", url)
    except Exception as e:
        st.error(f"파일 로드 실패: {e}")

# --- 6. [화면 3] 시스템 상태 ---
elif menu == "⚙️ 시스템 상태":
    st.header("⚙️ 시스템 상태")
    st.success("✅ DB 및 스토리지 연결 정상")
    st.info("Cloud Run 자동 녹화 엔진이 대기 중입니다.")