# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.5.1 (Dashboard Edition)
# DESCRIPTION: 상세 시간 표시, 로컬 가이드, 에러 방지 최적화
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
from datetime import datetime
import firebase_admin
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

st.set_page_config(page_title="Plant TI Center v2.5.1", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')

@st.cache_resource
def init_connections():
    try:
        get_app()
    except ValueError:
        cred_json = st.secrets.get("FIREBASE_SERVICE_ACCOUNT")
        bucket_name = st.secrets.get("FIREBASE_BUCKET_NAME")
        initialize_app(credentials.Certificate(json.loads(cred_json, strict=False)), {
            'storageBucket': bucket_name.replace("gs://", "")
        })
    s_url = st.secrets.get("SUPABASE_URL")
    s_key = st.secrets.get("SUPABASE_KEY")
    return create_client(s_url, s_key), storage.bucket()

supabase, bucket = init_connections()

# --- 사이드바: 브랜드 및 로컬 가이드 ---
st.sidebar.markdown(f"""<div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;"><h2 style="margin:0;">🏗️ DAEWOO E&C</h2><p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.5.1</p></div>""", unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

with st.sidebar.expander("🖥️ 로컬 하이브리드 사용법", expanded=True):
    st.markdown("""
    **순서대로 따라하세요:**
    1. **크롬 완전 종료**
    2. **디버깅 모드 실행**: `Win+R` 누른 후 입력
       `chrome.exe --remote-debugging-port=9222`
    3. **로그인**: 열린 크롬에서 웨비나 사이트 로그인 및 대기
    4. **녹화 시작**: 내 노트북 터미널에서 `python main.py` 실행
    """)

# --- [메뉴 1] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 웨비나 예약 및 상세 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 일정 등록")
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1: title = st.text_input("1. 웨비나 명칭")
        with col_t2: mode = st.selectbox("2. 모드", ["☁️ Cloud", "🖥️ Local"])
        
        url_input = st.text_input("3. 접속 URL")
        
        c1, c2, c3 = st.columns(3)
        with c1: rec_date = st.date_input("4. 녹화 날짜")
        with c2: rec_time = st.time_input("5. 녹화 시각")
        with c3: duration = st.number_input("6. 녹화 시간(분)", min_value=1, value=60)

        if st.button("🚀 예약 확정", use_container_width=True):
            if title and url_input:
                kst_dt = KST.localize(datetime.combine(rec_date, rec_time))
                supabase.table("webinar_reservations").insert({
                    "title": title, "webinar_url": url_input, "scheduled_at": kst_dt.isoformat(),
                    "duration_min": duration, "status": "pending", "rec_mode": mode.lower().split()[-1]
                }).execute()
                st.success("예약이 저장되었습니다.")
                st.rerun()

    st.divider()
    st.subheader("📊 예약 리스트 (상세 시간 포함)")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    
    for item in res.data:
        created = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
        scheduled = pd.to_datetime(item['scheduled_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
        mode_icon = "🖥️" if item.get('rec_mode') == 'local' else "☁️"
        
        with st.expander(f"{mode_icon} {item['title']} | {scheduled} 시작"):
            st.markdown(f"""
            - **📝 예약 등록 시각:** `{created}`
            - **⏰ 녹화 시작 시각:** `{scheduled}`
            - **🕒 녹화 지속 시간:** `{item['duration_min']}분`
            - **🔗 주소:** {item['webinar_url']}
            """)
            if st.button("🗑️ 일정 취소", key=f"can_{item['id']}"):
                supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                st.rerun()

# --- [메뉴 2] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 녹화 결과물 관리")
    res_db = supabase.table("webinar_reservations").select("*").execute()
    db_map = {item['video_url']: item for item in res_db.data if item.get('video_url')}
    blobs = list(bucket.list_blobs(prefix="webinars/"))
    blobs.sort(key=lambda x: x.updated, reverse=True)

    for blob in blobs:
        f_name = blob.name.replace("webinars/", "")
        db_item = db_map.get(blob.name, {})
        dl_count = db_item.get('download_count', 0)
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            with c1:
                st.write(f"**📺 {f_name}**")
                st.caption(f"📅 완료: {blob.updated.strftime('%Y-%m-%d %H:%M')} | 📥 {dl_count}회")
            with c2:
                import datetime as dt_url
                url = blob.generate_signed_url(expiration=dt_url.timedelta(minutes=60), response_disposition=f"attachment; filename={f_name}")
                if st.link_button("📥 저장", url, use_container_width=True):
                    if db_item.get('id'):
                        supabase.table("webinar_reservations").update({"download_count": dl_count + 1}).eq("id", db_item['id']).execute()
            with c3:
                if st.button("🗑️ 삭제", key=f"del_{blob.name}", use_container_width=True):
                    blob.delete()
                    if db_item.get('id'):
                        supabase.table("webinar_reservations").delete().eq("id", db_item['id']).execute()
                    st.rerun()
