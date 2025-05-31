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
# CloudType 환경에서는 외부 PostgreSQL 사용
if IS_CLOUDTYPE:
    # 외부 PostgreSQL 데이터베이스 연결
    DATABASE_URL = "postgresql+asyncpg://root:sunjea@svc.sel4.cloudtype.app:30173/testdb"
    print(f"CloudType 환경 감지: 외부 PostgreSQL 사용 ({DATABASE_URL})")
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
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# 테이블 생성
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
