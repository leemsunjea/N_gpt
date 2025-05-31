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
# 데이터베이스 URL 설정
# CloudType 환경에서는 외부 PostgreSQL 사용
if IS_CLOUDTYPE:
    # 외부 PostgreSQL 데이터베이스 연결
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
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/ngpt")
    print(f"로컬 환경: PostgreSQL 사용 ({DATABASE_URL})")

# 엔진 생성
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
        yield session
    except Exception as e:
        print(f"DB 세션 생성 오류: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        # 예외가 발생하더라도 세션은 반환해야 함
        if session:
            yield session
        else:
            # 연결 실패 시 빈 세션 반환
            print("대체 세션 생성")
            yield async_session()
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
