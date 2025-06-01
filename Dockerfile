FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 필수 파일만 복사
COPY *.py ./
COPY requirements.txt ./requirements.txt
COPY templates ./templates/
COPY start.sh ./
RUN chmod +x start.sh

# 필요한 디렉토리 생성
RUN mkdir -p static

# 필수 패키지만 설치
RUN pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# 포트 노출
EXPOSE 8000

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV CLOUDTYPE_DEPLOYMENT=1
ENV DB_USER=root
ENV DB_PASSWORD=sunjea
ENV DB_HOST=svc.sel4.cloudtype.app
ENV DB_PORT=30173
ENV DB_NAME=testdb

CMD ["./start.sh"]
