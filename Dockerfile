FROM python:3.11-slim AS build

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 최종 이미지 준비
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 시스템 패키지만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 필수 파일만 복사 (최소한의 파일만 포함)
COPY main.py chat_service.py document_processor.py lightweight_embedding.py database.py ./
COPY requirements-minimal.txt ./requirements.txt
COPY templates templates/
COPY start.sh ./
RUN chmod +x start.sh

# 필요한 디렉토리 생성
RUN mkdir -p static

# 필수 패키지만 설치 (최소한의 의존성)
RUN pip install --no-cache-dir fastapi uvicorn python-multipart jinja2 python-dotenv sqlalchemy asyncpg aiosqlite openai numpy PyPDF2 python-docx aiofiles && \
    pip cache purge

# 포트 노출
EXPOSE 8000

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV CLOUDTYPE_DEPLOYMENT=1
ENV DATABASE_URL=postgresql+asyncpg://root:sunjea@svc.sel4.cloudtype.app:30173/testdb

# 애플리케이션 실행
CMD ["./start.sh"]
