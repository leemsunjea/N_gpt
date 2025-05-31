#!/bin/bash
# CloudType 환경에서 필요한 라이브러리만 동적으로 설치

# 로그 디렉토리 생성
mkdir -p /tmp/logs

# 필요한 디렉토리 확인
mkdir -p templates static

echo "Installing required packages..."
# numpy는 필수적으로 필요합니다
pip install --no-cache-dir numpy==1.24.3

echo "Starting server with minimal dependencies..."

# FAISS와 SentenceTransformers는 필요할 때 지연 로딩됨
# 서버 시작
exec uvicorn main:app --host 0.0.0.0 --port $PORT
