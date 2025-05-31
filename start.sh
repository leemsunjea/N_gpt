#!/bin/bash
# CloudType 환경에서 필요한 라이브러리만 동적으로 설치

# 로그 디렉토리 생성
mkdir -p /tmp/logs

# 필요한 디렉토리 확인 및 권한 설정
mkdir -p templates static

# 패키지 설치 시도
echo "Installing required packages..."
pip install --no-cache-dir numpy==1.24.3 || echo "패키지 설치 실패, 계속 진행합니다."

echo "Starting server with minimal dependencies..."

# 환경 변수 설정 - 외부 PostgreSQL 데이터베이스 사용
export CLOUDTYPE_DEPLOYMENT=1
export PYTHONUNBUFFERED=1
export DATABASE_URL="postgresql+asyncpg://root:sunjea@svc.sel4.cloudtype.app:30173/testdb"

# 서버 시작
exec uvicorn main:app --host 0.0.0.0 --port $PORT
