#!/usr/bin/env python3
"""
기존 데이터베이스에 user_id 컬럼을 추가하는 마이그레이션 스크립트
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import engine, get_db_session
import uuid

async def migrate_add_user_id():
    """기존 데이터베이스에 user_id 컬럼을 추가하고 기존 데이터에 기본값 설정"""
    
    print("🔄 데이터베이스 마이그레이션 시작: user_id 컬럼 추가")
    
    async with engine.begin() as conn:
        # Document 테이블에 user_id 컬럼 추가 (이미 존재하면 무시)
        try:
            await conn.execute(text("""
                ALTER TABLE document ADD COLUMN user_id VARCHAR(255);
            """))
            print("✅ Document 테이블에 user_id 컬럼 추가 완료")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column name" in str(e).lower():
                print("ℹ️  Document 테이블의 user_id 컬럼이 이미 존재합니다")
            else:
                print(f"❌ Document 테이블 user_id 컬럼 추가 실패: {e}")
        
        # DocumentChunk 테이블에 user_id 컬럼 추가 (이미 존재하면 무시)
        try:
            await conn.execute(text("""
                ALTER TABLE documentchunk ADD COLUMN user_id VARCHAR(255);
            """))
            print("✅ DocumentChunk 테이블에 user_id 컬럼 추가 완료")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column name" in str(e).lower():
                print("ℹ️  DocumentChunk 테이블의 user_id 컬럼이 이미 존재합니다")
            else:
                print(f"❌ DocumentChunk 테이블 user_id 컬럼 추가 실패: {e}")
        
        # 기존 데이터에 기본 user_id 할당
        default_user_id = "legacy_user_" + str(uuid.uuid4())[:8]
        
        try:
            # NULL user_id를 가진 Document 레코드 업데이트
            result = await conn.execute(text("""
                UPDATE document 
                SET user_id = :user_id 
                WHERE user_id IS NULL;
            """), {"user_id": default_user_id})
            
            print(f"✅ Document 테이블의 기존 레코드 {result.rowcount}개에 user_id '{default_user_id}' 할당")
            
            # NULL user_id를 가진 DocumentChunk 레코드 업데이트
            result = await conn.execute(text("""
                UPDATE documentchunk 
                SET user_id = :user_id 
                WHERE user_id IS NULL;
            """), {"user_id": default_user_id})
            
            print(f"✅ DocumentChunk 테이블의 기존 레코드 {result.rowcount}개에 user_id '{default_user_id}' 할당")
            
        except Exception as e:
            print(f"❌ 기존 데이터 user_id 할당 실패: {e}")
        
        # 인덱스 생성 (이미 존재하면 무시)
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_document_user_id ON document(user_id);
            """))
            print("✅ Document 테이블에 user_id 인덱스 생성 완료")
        except Exception as e:
            print(f"❌ Document 테이블 user_id 인덱스 생성 실패: {e}")
        
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documentchunk_user_id ON documentchunk(user_id);
            """))
            print("✅ DocumentChunk 테이블에 user_id 인덱스 생성 완료")
        except Exception as e:
            print(f"❌ DocumentChunk 테이블 user_id 인덱스 생성 실패: {e}")
    
    print("🎉 데이터베이스 마이그레이션 완료!")
    
    # 마이그레이션 결과 확인
    async with get_db_session() as session:
        try:
            # Document 테이블 현황 확인
            result = await session.execute(text("SELECT COUNT(*) as total, COUNT(user_id) as with_user_id FROM document"))
            doc_stats = result.fetchone()
            print(f"📊 Document 테이블: 전체 {doc_stats.total}개, user_id 있음 {doc_stats.with_user_id}개")
            
            # DocumentChunk 테이블 현황 확인
            result = await session.execute(text("SELECT COUNT(*) as total, COUNT(user_id) as with_user_id FROM documentchunk"))
            chunk_stats = result.fetchone()
            print(f"📊 DocumentChunk 테이블: 전체 {chunk_stats.total}개, user_id 있음 {chunk_stats.with_user_id}개")
            
        except Exception as e:
            print(f"❌ 마이그레이션 결과 확인 실패: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_add_user_id())
