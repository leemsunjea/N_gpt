import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from datetime import datetime

# CloudType 환경 감지
IS_CLOUDTYPE = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'

# 데이터베이스 URL 설정
if IS_CLOUDTYPE:
    # CloudType 환경: 외부 PostgreSQL 사용
    # 환경 변수에서 직접 가져오기
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        # 개별 환경 변수로 구성
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "sunjea")
        DB_HOST = os.getenv("DB_HOST", "svc.sel4.cloudtype.app")
        DB_PORT = os.getenv("DB_PORT", "30173")
        DB_NAME = os.getenv("DB_NAME", "testdb")
        DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    print(f"CloudType 환경 감지: 외부 PostgreSQL 사용 ({DATABASE_URL})")
    print(f"환경 변수: CLOUDTYPE_DEPLOYMENT={os.environ.get('CLOUDTYPE_DEPLOYMENT')}")
    print(f"환경 변수: DATABASE_URL={os.environ.get('DATABASE_URL')}")
else:
    # 로컬 환경: SQLite 사용 (더 간단하고 안정적)
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ngpt.db")
    print(f"로컬 환경: SQLite 사용 ({DATABASE_URL})")

# 엔진 생성
if IS_CLOUDTYPE:
    # CloudType 환경에서는 연결 풀 옵션 조정
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        connect_args={
            "timeout": 180,  # 'connect_timeout'에서 'timeout'으로 변경
            "command_timeout": 180,
            "server_settings": {
                "application_name": "N_GPT_CloudType",
                "jit": "off"
            }
        }
    )
else:
    # 로컬 환경
    engine = create_async_engine(DATABASE_URL, echo=True)

# 세션 팩토리
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Base 클래스
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)  # UUID 문자열
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)  # 사용자 ID 추가 (인덱싱)
    filename = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON 형태로 저장
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # 정렬용 인덱스 추가

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)  # 사용자 ID 추가 (인덱싱)
    document_id = Column(Integer, nullable=False, index=True)  # 조인용 인덱스 추가
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON 형태로 저장
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# 데이터베이스 의존성
async def get_db():
    session = async_session()
    try:
        yield session
    except Exception as e:
        print(f"DB 세션 생성 오류: {str(e)}")
        import traceback
        print(traceback.format_exc())
        await session.rollback()
        raise  # 예외를 다시 발생시켜 FastAPI가 처리하도록 함
    finally:
        await session.close()
        
# 테이블 생성
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
