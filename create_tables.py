#!/usr/bin/env python3
"""
데이터베이스 테이블 생성 스크립트
CloudType 환경에서 필요한 테이블들을 생성합니다.
"""

import asyncio
import os

async def create_tables():
    """필요한 테이블들을 생성합니다."""
    
    try:
        import asyncpg
        print("asyncpg 모듈 로드 성공")
    except ImportError:
        print("asyncpg 모듈이 설치되지 않았습니다. 설치 중...")
        import subprocess
        subprocess.check_call(["pip", "install", "asyncpg"])
        import asyncpg
        print("asyncpg 설치 완료")
    
    # CloudType 데이터베이스 연결 정보
    DB_USER = "root"
    DB_PASSWORD = "sunjea"
    DB_HOST = "svc.sel4.cloudtype.app"
    DB_PORT = 30173
    DB_NAME = "testdb"
    
    print(f"데이터베이스 연결 중: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    try:
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT
        )
        
        print("데이터베이스 연결 성공!")
        
        # documents 테이블 생성
        documents_sql = """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            filename VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
        );
        """
        
        # document_chunks 테이블 생성  
        chunks_sql = """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding TEXT,
            chunk_index INTEGER NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC')
        );
        """
        
        # 인덱스 생성
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
        CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_index ON document_chunks(chunk_index);
        """
        
        print("documents 테이블 생성 중...")
        await conn.execute(documents_sql)
        print("documents 테이블 생성 완료!")
        
        print("document_chunks 테이블 생성 중...")
        await conn.execute(chunks_sql)
        print("document_chunks 테이블 생성 완료!")
        
        print("인덱스 생성 중...")
        await conn.execute(index_sql)
        print("인덱스 생성 완료!")
        
        # 테이블 목록 확인
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        print("\n=== 현재 데이터베이스 테이블 목록 ===")
        for table in tables:
            print(f"- {table['table_name']}")
            
        # documents 테이블 스키마 확인
        documents_schema = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'documents' 
            ORDER BY ordinal_position;
        """)
        
        print("\n=== documents 테이블 스키마 ===")
        for col in documents_schema:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"{col['column_name']:15} | {col['data_type']:20} | {nullable}")
            
        # document_chunks 테이블 스키마 확인
        chunks_schema = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks' 
            ORDER BY ordinal_position;
        """)
        
        print("\n=== document_chunks 테이블 스키마 ===")
        for col in chunks_schema:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"{col['column_name']:15} | {col['data_type']:20} | {nullable}")
        
        await conn.close()
        print("\n✅ 테이블 생성이 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_tables())
