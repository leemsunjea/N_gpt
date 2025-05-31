import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

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
            "timeout": 60,  # 'connect_timeout'에서 'timeout'으로 변경
            "command_timeout": 60,
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

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON 형태로 저장
    created_at = Column(DateTime, default=datetime.utcnow)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # JSON 형태로 저장
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# 데이터베이스 의존성
async def get_db():
    session = None
    try:
        session = async_session()
        print("DB 세션 생성 성공")
        
        # CloudType 환경에서는 연결 테스트를 건너뛰고 오프라인 모드로 동작
        if IS_CLOUDTYPE:
            print("CloudType 환경: 오프라인 모드로 동작 (연결 테스트 건너뜀)")
            yield session
            return
        
        # 로컬 환경에서만 연결 테스트
        try:
            # 간단한 연결 테스트
            await session.execute("SELECT 1")
            print("DB 연결 테스트 성공")
        except Exception as test_error:
            print(f"DB 연결 테스트 실패: {str(test_error)}")
            # 연결 실패 시에도 세션은 반환 (오프라인 모드)
        
        yield session
        
    except Exception as e:
        print(f"DB 세션 생성 오류: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        # 연결 실패 시에도 세션은 반환 (오프라인 모드)
        if session is None:
            session = async_session()
            print("대체 세션 생성")
        yield session
        
    finally:
        if session:
            try:
                await session.close()
                print("DB 세션 닫기 성공")
            except Exception as e:
                print(f"DB 세션 닫기 오류: {str(e)}")

# 테이블 생성
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
