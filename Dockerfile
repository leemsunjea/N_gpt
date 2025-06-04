FROM python:3.11-slim AS builder

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
    swig \
    cmake \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Builder stage: copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --prefix=/install \
    && pip cache purge

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code and assets
COPY *.py ./
COPY templates ./templates/
COPY start.sh ./
RUN chmod +x start.sh
# 필요한 디렉토리 생성
RUN mkdir -p static

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
