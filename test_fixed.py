#!/usr/bin/env python3
"""
테이블 생성과 텍스트 정제 기능 테스트
"""

import asyncio
import os
import traceback

# CloudType 환경 설정
os.environ['CLOUDTYPE_DEPLOYMENT'] = '1'
os.environ['DB_USER'] = 'root'
os.environ['DB_PASSWORD'] = 'sunjea'
os.environ['DB_HOST'] = 'svc.sel4.cloudtype.app'
os.environ['DB_PORT'] = '30173'
os.environ['DB_NAME'] = 'testdb'

def test_text_cleaning():
    """텍스트 정제 테스트"""
    print("\n=== 텍스트 정제 테스트 ===")
    
    try:
        from text_cleaner import TextCleaner
        
        # NULL 바이트가 포함된 테스트 텍스트
        test_text = "안녕하세요\x00이것은 테스트\ufffd텍스트입니다\x00"
        print(f"원본 텍스트: {repr(test_text)}")
        
        # 정제 전 확인
        has_null_before = '\x00' in test_text
        print(f"정제 전 NULL 바이트 존재: {has_null_before}")
        
        # 텍스트 정제
        cleaned_text = TextCleaner.clean_for_postgresql(test_text)
        print(f"정제된 텍스트: {repr(cleaned_text)}")
        
        # 정제 후 확인
        has_null_after = '\x00' in cleaned_text
        print(f"정제 후 NULL 바이트 존재: {has_null_after}")
        
        # UTF-8 유효성 확인
        is_valid_utf8 = TextCleaner.validate_utf8(cleaned_text)
        print(f"UTF-8 유효성: {is_valid_utf8}")
        
        if not has_null_after and is_valid_utf8:
            print("✅ 텍스트 정제 성공!")
            return True
        else:
            print("❌ 텍스트 정제 실패!")
            return False
    except Exception as e:
        print(f"❌ 텍스트 정제 테스트 실패: {e}")
        traceback.print_exc()
        return False

async def test_table_creation():
    """테이블 생성 테스트"""
    print("=== 테이블 생성 테스트 ===")
    
    try:
        from database import create_tables, engine
        from sqlalchemy import text
        
        print("1. 테이블 생성 중...")
        await create_tables()
        print("✅ 테이블 생성 성공!")
        
        # 테이블 목록 확인
        print("2. 테이블 목록 확인 중...")
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """))
            tables = result.fetchall()
            table_names = [t[0] for t in tables]
            print(f"현재 테이블 목록: {table_names}")
            
            # 필요한 테이블 확인
            required_tables = ['documents', 'document_chunks']
            missing_tables = [t for t in required_tables if t not in table_names]
            
            if missing_tables:
                print(f"❌ 누락된 테이블: {missing_tables}")
                return False
            else:
                print("✅ 모든 필요한 테이블이 존재합니다!")
                return True
                
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")
        traceback.print_exc()
        return False

async def test_database_insertion():
    """데이터베이스 삽입 테스트"""
    print("\n=== 데이터베이스 삽입 테스트 ===")
    
    try:
        from database import async_session, Document, DocumentChunk
        from text_cleaner import TextCleaner
        
        # 테스트 텍스트 (NULL 바이트 포함)
        test_content = "테스트 문서\x00내용입니다\ufffd"
        cleaned_content = TextCleaner.clean_for_postgresql(test_content)
        
        print("1. 데이터베이스 세션 생성 중...")
        async with async_session() as session:
            # 테스트 문서 삽입
            print("2. 테스트 문서 삽입 중...")
            document = Document(
                filename="test_document.txt",
                content=cleaned_content
            )
            session.add(document)
            await session.flush()
            
            print(f"✅ 문서 삽입 성공! ID: {document.id}")
            
            # 테스트 청크 삽입
            print("3. 테스트 청크 삽입 중...")
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_text=cleaned_content,
                chunk_index=0
            )
            session.add(chunk)
            await session.commit()
            
            print(f"✅ 청크 삽입 성공! ID: {chunk.id}")
            
            # 삽입된 데이터 확인
            print("4. 삽입된 데이터 확인 중...")
            result_doc = await session.get(Document, document.id)
            result_chunk = await session.get(DocumentChunk, chunk.id)
            
            print(f"문서 파일명: {result_doc.filename}")
            print(f"문서 내용: {repr(result_doc.content)}")
            print(f"청크 텍스트: {repr(result_chunk.chunk_text)}")
            
            # NULL 바이트 확인
            has_null_doc = '\x00' in result_doc.content
            has_null_chunk = '\x00' in result_chunk.chunk_text
            
            if not has_null_doc and not has_null_chunk:
                print("✅ 데이터베이스 삽입 성공! NULL 바이트 없음")
                return True
            else:
                print("❌ NULL 바이트가 여전히 존재함")
                return False
                
    except Exception as e:
        print(f"❌ 데이터베이스 삽입 실패: {e}")
        traceback.print_exc()
        return False

async def main():
    """메인 테스트 함수"""
    print("🔧 PostgreSQL 문제 해결 테스트 시작\n")
    
    # 1. 텍스트 정제 테스트
    text_test_ok = test_text_cleaning()
    
    # 2. 테이블 생성 테스트
    table_test_ok = await test_table_creation()
    
    # 3. 데이터베이스 삽입 테스트 (테이블이 성공적으로 생성된 경우에만)
    db_test_ok = False
    if table_test_ok:
        db_test_ok = await test_database_insertion()
    
    # 결과 요약
    print("\n" + "="*50)
    print("📊 테스트 결과 요약")
    print("="*50)
    print(f"텍스트 정제: {'✅ 성공' if text_test_ok else '❌ 실패'}")
    print(f"테이블 생성: {'✅ 성공' if table_test_ok else '❌ 실패'}")
    print(f"DB 삽입: {'✅ 성공' if db_test_ok else '❌ 실패'}")
    
    if text_test_ok and table_test_ok and db_test_ok:
        print("\n🎉 모든 테스트 성공! 문서 업로드가 정상 동작할 것입니다.")
    else:
        print("\n⚠️ 일부 테스트 실패. 문제를 해결해야 합니다.")
    
    return text_test_ok and table_test_ok and db_test_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
