# ==========================================
# SYSTEM: Plant TI Team Webinar Master
# VERSION: v2.3.8 (Enhanced Status Edition)
# DESCRIPTION: 예약 목록에 녹화 지속 시간 표시 추가
# ==========================================

import streamlit as st
import os
import json
import pandas as pd
import pytz
import datetime as dt
from datetime import datetime
import firebase_admin
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

st.set_page_config(page_title="Plant TI Center v2.3.8", page_icon="🎥", layout="wide")
load_dotenv()
KST = pytz.timezone('Asia/Seoul')

WORLD_ZONES = {
    "대한민국 (KST)": "Asia/Seoul",
    "미국 동부 (EST/EDT)": "America/New_York",
    "미국 서부 (PST/PDT)": "America/Los_Angeles",
    "영국 (GMT/BST)": "Europe/London",
    "독일/프랑스 (CET/CEST)": "Europe/Paris",
    "싱가포르/대만 (CST)": "Asia/Singapore",
    "일본 (JST)": "Asia/Tokyo"
}

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

# UI 스타일 설정
st.markdown("""
    <style>
    .time-box { background-color: #f0f7ff; padding: 20px; border-radius: 12px; border: 2px solid #003399; }
    .kst-highlight { color: #FF5733; font-weight: 900; font-size: 24px; }
    .created-at { font-size: 11px; color: #888; }
    .duration-tag { background-color: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 5px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"""
    <div style="background-color: #003399; padding: 15px; border-radius: 10px; text-align: center; color: white;">
        <h2 style="margin:0;">🏗️ DAEWOO E&C</h2>
        <p style="margin:0; font-size: 14px; opacity: 0.8;">Plant TI Team v2.3.8</p>
    </div>
    """, unsafe_allow_html=True)

menu = st.sidebar.radio("메뉴", ["📅 예약 및 현황", "🎥 녹화 완료 파일"])

# --- 1. [메뉴] 예약 및 현황 ---
if menu == "📅 예약 및 현황":
    st.title("📅 글로벌 예약 및 실시간 현황")
    
    with st.container(border=True):
        st.subheader("📝 신규 일정 등록")
        title = st.text_input("1. 웨비나 명칭")
        url_input = st.text_input("2. 접속 URL")
        
        c1, c2 = st.columns(2)
        with c1: selected_zone = st.selectbox("3. 개최지 타임존", list(WORLD_ZONES.keys()))
        with c2: duration = st.number_input("4. 녹화 시간(분)", min_value=1, value=60)
        
        col_d, col_t = st.columns(2)
        with col_d: rec_date = st.date_input("5. 현지 시작 날짜")
        with col_t: rec_time = st.time_input("6. 현지 시작 시각")

        target_tz = pytz.timezone(WORLD_ZONES[selected_zone])
        kst_dt = target_tz.localize(datetime.combine(rec_date, rec_time)).astimezone(KST)
        
        st.markdown(f"""
            <div class="time-box">
                <span style="color:gray;">🚀 실제 녹화 시작 (한국 시각 KST):</span><br>
                <span class="kst-highlight">{kst_dt.strftime("%Y-%m-%d %H:%M")}</span>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 예약 확정", use_container_width=True):
            supabase.table("webinar_reservations").insert({
                "title": title, "webinar_url": url_input, "scheduled_at": kst_dt.isoformat(),
                "duration_min": duration, "status": "pending", "download_count": 0
            }).execute()
            st.success(f"'{title}' 일정이 {duration}분 녹화로 예약되었습니다.")
            st.rerun()

    st.divider()
    st.subheader("📊 대기 및 진행 중인 일정")
    res = supabase.table("webinar_reservations").select("*").in_("status", ["pending", "running"]).order("scheduled_at").execute()
    
    if not res.data:
        st.info("현재 대기 중인 예약 일정이 없습니다.")
    else:
        for item in res.data:
            s_kst = pd.to_datetime(item['scheduled_at']).astimezone(KST)
            created = pd.to_datetime(item['created_at']).astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            # [v2.3.8 업데이트] 제목에 녹화 시간(duration_min) 표시
            display_title = f"[{item['status'].upper()}] {item['title']} | 🕒 {item['duration_min']}분 녹화"
            
            with st.expander(display_title):
                st.write(f"🔗 **URL:** {item['webinar_url']}")
                st.write(f"⏰ **한국 시작:** {s_kst.strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"<p class='created-at'>🕒 예약 등록일: {created}</p>", unsafe_allow_html=True)
                if st.button("🗑️ 일정 취소", key=f"can_{item['id']}", use_container_width=True):
                    supabase.table("webinar_reservations").delete().eq("id", item['id']).execute()
                    st.rerun()

# --- 2. [메뉴] 녹화 완료 파일 ---
elif menu == "🎥 녹화 완료 파일":
    st.title("🎥 결과 관리 및 노트북 저장")
    res_db = supabase.table("webinar_reservations").select("*").execute()
    db_map = {item['video_url']: item for item in res_db.data if item.get('video_url')}
    blobs = list(bucket.list_blobs(prefix="webinars/"))
    blobs.sort(key=lambda x: x.updated, reverse=True)

    if not blobs:
        st.info("보관 중인 녹화 본이 없습니다.")
    else:
        for blob in blobs:
            f_name = blob.name.replace("webinars/", "")
            db_item = db_map.get(blob.name, {})
            dl_count = db_item.get('download_count', 0)
            reg_date = pd.to_datetime(db_item.get('created_at', blob.updated)).astimezone(KST).strftime('%Y-%m-%d %H:%M')
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 1, 1])
                with c1:
                    st.write(f"**📺 {f_name}**")
                    # 완료 리스트에서도 몇 분짜리 영상인지 표시
                    duration_info = f" | 🕒 {db_item.get('duration_min', '?')}분"
                    st.caption(f"📅 완료: {blob.updated.strftime('%Y-%m-%d %H:%M')}{duration_info} | 📥 {dl_count}회")
                    st.markdown(f"<p class='created-at'>📝 시스템 등록 시점: {reg_date}</p>", unsafe_allow_html=True)
                with c2:
                    url = blob.generate_signed_url(expiration=dt.timedelta(minutes=60), response_disposition=f"attachment; filename={f_name}")
                    if st.link_button("📥 저장", url, use_container_width=True):
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").update({"download_count": dl_count + 1}).eq("id", db_item['id']).execute()
                with c3:
                    if st.button("🗑️ 삭제", key=f"del_{blob.name}", type="secondary", use_container_width=True):
                        blob.delete()
                        if db_item.get('id'):
                            supabase.table("webinar_reservations").delete().eq("id", db_item['id']).execute()
                        st.rerun()
