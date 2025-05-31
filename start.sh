#!/bin/bash
# CloudType 환경에서 필요한 라이브러리만 동적으로 설치

# 로그 디렉토리 생성
mkdir -p /tmp/logs

# 필요한 디렉토리 확인
mkdir -p templates static

echo "Installing required packages..."
# 시스템 레벨에서 설치를 시도합니다 (권한 문제 해결)
pip install --no-cache-dir numpy==1.24.3 aiosqlite==0.19.0 || echo "패키지 설치 실패, 계속 진행합니다."

echo "Starting server with minimal dependencies..."

# 환경 변수 설정
export CLOUDTYPE_DEPLOYMENT=1

# 서버 시작
exec uvicorn main:app --host 0.0.0.0 --port $PORT
