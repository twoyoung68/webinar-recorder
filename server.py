import os
import firebase_admin
from firebase_admin import credentials
import json
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

# [공통 인증 로직]
if not firebase_admin._apps:
    firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if firebase_json:
        info = json.loads(firebase_json, strict=False)
        cred = credentials.Certificate(info)
    else:
        json_path = os.path.join(os.path.dirname(__file__), 'firebase_key.json')
        if os.path.exists(json_path):
            cred = credentials.Certificate(json_path)
        else:
            print("⚠️ Firebase key not found - check your files or env vars")
            cred = None
    
    if cred:
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'webinar-recorder.firebasestorage.app'
        })

is_running = False 

@app.route("/", methods=["POST"])
def handle_trigger():
    global is_running
    if is_running:
        return jsonify({"status": "ignored", "message": "Already running"}), 200

    print("🚀 구글 신호 수신! 순찰을 시작합니다.")
    is_running = True
    try:
        # main.py를 비동기로 실행
        subprocess.Popen(["python", "main.py"])
    finally:
        is_running = False 
    
    return jsonify({"status": "success", "message": "Robot activated"}), 200

if __name__ == "__main__":
    # 구글 클라우드 필수 설정: PORT 환경 변수 확인
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)