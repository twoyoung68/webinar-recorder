# app.py
import os
import json
from flask import Flask, render_template, redirect, url_for
from firebase_admin import storage, credentials, initialize_app, get_app
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# 초기화
try:
    get_app()
except ValueError:
    cred_info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"))
    initialize_app(credentials.Certificate(cred_info), {'storageBucket': os.getenv('FIREBASE_BUCKET_NAME')})

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
bucket = storage.bucket()

@app.route('/')
def index():
    blobs = bucket.list_blobs(prefix="webinars/")
    files = []
    for b in blobs:
        files.append({
            'name': b.name.replace("webinars/", ""),
            'full_path': b.name,
            'size': f"{round(b.size / (1024*1024), 2)}MB",
            'updated': b.updated.strftime('%Y-%m-%d %H:%M')
        })
    # 간단한 HTML 템플릿 반환 (실제로는 templates/index.html로 분리 권장)
    html = """
    <h1>Plant TI Webinar Gold Safe</h1>
    <table border="1">
        <tr><th>파일명</th><th>크기</th><th>날짜</th><th>관리</th></tr>
        {% for f in files %}
        <tr>
            <td>{{ f.name }}</td><td>{{ f.size }}</td><td>{{ f.updated }}</td>
            <td>
                <a href="/download/{{ f.name }}">⬇️다운로드</a> | 
                <a href="/delete/{{ f.name }}" onclick="return confirm('삭제할까요?')">❌삭제</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    """
    from flask import render_template_string
    return render_template_string(html, files=files)

@app.route('/download/<path:filename>')
def download(filename):
    blob = bucket.blob(f"webinars/{filename}")
    url = blob.generate_signed_url(expiration=600) # 10분 유효 링크
    return redirect(url)

@app.route('/delete/<path:filename>')
def delete(filename):
    # 1. 스토리지 삭제
    bucket.blob(f"webinars/{filename}").delete()
    # 2. Supabase 경로 초기화
    supabase.table("webinar_reservations").update({"video_url": None}).eq("video_url", f"webinars/{filename}").execute()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
