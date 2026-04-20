# 1. 파이썬 3.11 슬림 버전 사용 (빌드 속도 향상)
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 필수 파일 복사 및 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 나머지 소스 코드 복사
COPY . .

# 5. 포트 설정 (Cloud Run은 반드시 8080)
EXPOSE 8080

# 6. Streamlit 실행 (0.0.0.0 주소와 8080 포트 고정)
CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]