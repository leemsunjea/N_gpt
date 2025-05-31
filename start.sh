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

# 데이터베이스 연결 환경 변수
export DB_USER=${DB_USER:-"root"}
export DB_PASSWORD=${DB_PASSWORD:-"sunjea"}
export DB_HOST=${DB_HOST:-"svc.sel4.cloudtype.app"}
export DB_PORT=${DB_PORT:-"30173"}
export DB_NAME=${DB_NAME:-"testdb"}

# 연결 테스트용 로깅
echo "데이터베이스 연결 정보:"
echo "DB_USER: $DB_USER"
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"
echo "DB_NAME: $DB_NAME"

# 서버 시작
echo "서버 시작 중..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT --log-level debug
