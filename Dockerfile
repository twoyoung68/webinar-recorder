# 1. '완제품' 이미지를 사용 (외부 다운로드 최소화)
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# 2. 캐시를 활용하여 라이브러리 설치 (실패 시 여기서 멈추게 함)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || exit 1

# 3. 브라우저 설치 (install-deps 생략, 이미 들어있음)
RUN playwright install chromium || exit 1

# 4. 코드 복사 (가장 마지막에 수행)
COPY . .

# 5. 구글 클라우드 규격 고정
ENV PORT 8080
EXPOSE 8080
CMD ["python", "server.py"]