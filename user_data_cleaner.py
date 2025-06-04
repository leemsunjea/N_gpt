#!/usr/bin/env python3
"""
사용자 데이터 정리 유틸리티
- 비활성 사용자의 FAISS 인덱스 파일 삭제
- 오래된 세션 데이터 정리
- 사용자별 데이터 통계 조회
"""

import asyncio
import os
import glob
import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, text
from database import get_db_session, Document, DocumentChunk
from user_session import UserSessionManager

class UserDataCleaner:
    def __init__(self):
        self.faiss_index_dir = "faiss_indexes"
    
    async def get_all_user_stats(self):
        """모든 사용자의 통계 조회"""
        async with get_db_session() as session:
            # 사용자별 문서 및 청크 수 조회
            result = await session.execute(text("""
                SELECT 
                    d.user_id,
                    COUNT(DISTINCT d.id) as document_count,
                    COUNT(dc.id) as chunk_count,
                    MAX(d.created_at) as last_document_upload
                FROM document d 
                LEFT JOIN documentchunk dc ON d.id = dc.document_id 
                WHERE d.user_id IS NOT NULL
                GROUP BY d.user_id
                ORDER BY last_document_upload DESC
            """))
            
            users_data = []
            for row in result:
                user_data = {
                    "user_id": row.user_id,
                    "document_count": row.document_count,
                    "chunk_count": row.chunk_count,
                    "last_document_upload": row.last_document_upload.isoformat() if row.last_document_upload else None,
                    "has_faiss_index": self.check_faiss_index_exists(row.user_id)
                }
                users_data.append(user_data)
            
            print(f"📊 총 {len(users_data)}명의 사용자 발견")
            return users_data
    
    def check_faiss_index_exists(self, user_id: str) -> bool:
        """사용자의 FAISS 인덱스 파일 존재 여부 확인"""
        if not os.path.exists(self.faiss_index_dir):
            return False
        
        pattern = os.path.join(self.faiss_index_dir, f"{user_id}_*.index")
        return len(glob.glob(pattern)) > 0
    
    def get_faiss_index_files(self, user_id: str) -> list:
        """사용자의 FAISS 인덱스 파일 목록 반환"""
        if not os.path.exists(self.faiss_index_dir):
            return []
        
        pattern = os.path.join(self.faiss_index_dir, f"{user_id}_*")
        return glob.glob(pattern)
    
    async def cleanup_inactive_users(self, days_threshold: int = 30) -> dict:
        """비활성 사용자 데이터 정리"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        print(f"🧹 {days_threshold}일 이상 비활성 사용자 데이터 정리 시작")
        print(f"기준 날짜: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        stats = {
            "inactive_users": 0,
            "deleted_documents": 0,
            "deleted_chunks": 0,
            "deleted_faiss_files": 0,
            "errors": []
        }
        
        try:
            # 비활성 사용자 찾기
            async with get_db_session() as session:
                result = await session.execute(text("""
                    SELECT user_id, COUNT(*) as doc_count, MAX(created_at) as last_activity
                    FROM document 
                    WHERE user_id IS NOT NULL 
                    AND created_at < :cutoff_date
                    GROUP BY user_id
                """), {"cutoff_date": cutoff_date})
                
                inactive_users = result.fetchall()
                
                for user_data in inactive_users:
                    user_id = user_data.user_id
                    doc_count = user_data.doc_count
                    last_activity = user_data.last_activity
                    
                    print(f"🗑️  사용자 {user_id} 정리 중... (문서 {doc_count}개, 마지막 활동: {last_activity})")
                    
                    try:
                        # 1. DocumentChunk 삭제
                        chunk_result = await session.execute(
                            delete(DocumentChunk).where(DocumentChunk.user_id == user_id)
                        )
                        stats["deleted_chunks"] += chunk_result.rowcount
                        
                        # 2. Document 삭제
                        doc_result = await session.execute(
                            delete(Document).where(Document.user_id == user_id)
                        )
                        stats["deleted_documents"] += doc_result.rowcount
                        
                        # 3. FAISS 인덱스 파일 삭제
                        faiss_files = self.get_faiss_index_files(user_id)
                        for file_path in faiss_files:
                            try:
                                os.remove(file_path)
                                stats["deleted_faiss_files"] += 1
                                print(f"  ✅ FAISS 파일 삭제: {file_path}")
                            except Exception as e:
                                error_msg = f"FAISS 파일 삭제 실패 ({file_path}): {e}"
                                print(f"  ❌ {error_msg}")
                                stats["errors"].append(error_msg)
                        
                        stats["inactive_users"] += 1
                        print(f"  ✅ 사용자 {user_id} 데이터 정리 완료")
                        
                    except Exception as e:
                        error_msg = f"사용자 {user_id} 데이터 정리 실패: {e}"
                        print(f"  ❌ {error_msg}")
                        stats["errors"].append(error_msg)
                
                await session.commit()
        
        except Exception as e:
            error_msg = f"데이터 정리 중 오류 발생: {e}"
            print(f"❌ {error_msg}")
            stats["errors"].append(error_msg)
        
        print(f"🎉 데이터 정리 완료: {stats}")
        return stats
    
    async def cleanup_orphaned_faiss_files(self) -> dict:
        """고아 FAISS 파일 정리 (DB에 사용자 데이터는 없지만 FAISS 파일만 남은 경우)"""
        if not os.path.exists(self.faiss_index_dir):
            return {"deleted_files": 0, "errors": []}
        
        print("🧹 고아 FAISS 파일 정리 시작")
        
        stats = {"deleted_files": 0, "errors": []}
        
        try:
            # DB에서 활성 사용자 ID 목록 가져오기
            async with get_db_session() as session:
                result = await session.execute(
                    select(Document.user_id).distinct().where(Document.user_id.isnot(None))
                )
                active_user_ids = {row.user_id for row in result}
                print(f"📊 활성 사용자 {len(active_user_ids)}명 발견")
            
            # FAISS 디렉토리의 모든 파일 확인
            all_faiss_files = glob.glob(os.path.join(self.faiss_index_dir, "*"))
            
            for file_path in all_faiss_files:
                filename = os.path.basename(file_path)
                
                # 파일명에서 user_id 추출 (user_id_*.index 또는 user_id_*.pkl 형태)
                user_id = None
                for active_id in active_user_ids:
                    if filename.startswith(f"{active_id}_"):
                        user_id = active_id
                        break
                
                # 활성 사용자와 연결되지 않은 파일이면 삭제
                if user_id is None:
                    try:
                        os.remove(file_path)
                        stats["deleted_files"] += 1
                        print(f"  🗑️  고아 파일 삭제: {filename}")
                    except Exception as e:
                        error_msg = f"고아 파일 삭제 실패 ({filename}): {e}"
                        print(f"  ❌ {error_msg}")
                        stats["errors"].append(error_msg)
        
        except Exception as e:
            error_msg = f"고아 파일 정리 중 오류 발생: {e}"
            print(f"❌ {error_msg}")
            stats["errors"].append(error_msg)
        
        print(f"🎉 고아 파일 정리 완료: {stats}")
        return stats

async def main():
    """메인 실행 함수"""
    cleaner = UserDataCleaner()
    
    print("=" * 50)
    print("🛠️  N_GPT 사용자 데이터 정리 도구")
    print("=" * 50)
    
    while True:
        print("\n선택하세요:")
        print("1. 모든 사용자 통계 조회")
        print("2. 비활성 사용자 데이터 정리 (30일 기준)")
        print("3. 비활성 사용자 데이터 정리 (사용자 정의 기간)")
        print("4. 고아 FAISS 파일 정리")
        print("5. 종료")
        
        choice = input("\n번호를 입력하세요: ").strip()
        
        if choice == "1":
            print("\n📊 사용자 통계 조회 중...")
            users_stats = await cleaner.get_all_user_stats()
            
            if users_stats:
                print(f"\n{'사용자 ID':<40} {'문서':<8} {'청크':<8} {'FAISS':<8} {'마지막 업로드':<20}")
                print("-" * 90)
                for user in users_stats:
                    faiss_status = "✅" if user["has_faiss_index"] else "❌"
                    last_upload = user["last_document_upload"][:19] if user["last_document_upload"] else "없음"
                    print(f"{user['user_id']:<40} {user['document_count']:<8} {user['chunk_count']:<8} {faiss_status:<8} {last_upload:<20}")
            else:
                print("사용자가 없습니다.")
        
        elif choice == "2":
            print("\n🧹 비활성 사용자 데이터 정리 (30일 기준)...")
            confirm = input("정말로 30일 이상 비활성 사용자 데이터를 삭제하시겠습니까? (y/N): ")
            if confirm.lower() == 'y':
                stats = await cleaner.cleanup_inactive_users(30)
                print(f"\n정리 완료: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            else:
                print("취소되었습니다.")
        
        elif choice == "3":
            try:
                days = int(input("비활성 기준 일수를 입력하세요: "))
                if days <= 0:
                    print("❌ 양수를 입력해주세요.")
                    continue
                
                print(f"\n🧹 비활성 사용자 데이터 정리 ({days}일 기준)...")
                confirm = input(f"정말로 {days}일 이상 비활성 사용자 데이터를 삭제하시겠습니까? (y/N): ")
                if confirm.lower() == 'y':
                    stats = await cleaner.cleanup_inactive_users(days)
                    print(f"\n정리 완료: {json.dumps(stats, indent=2, ensure_ascii=False)}")
                else:
                    print("취소되었습니다.")
            except ValueError:
                print("❌ 올바른 숫자를 입력해주세요.")
        
        elif choice == "4":
            print("\n🧹 고아 FAISS 파일 정리...")
            confirm = input("정말로 고아 FAISS 파일을 삭제하시겠습니까? (y/N): ")
            if confirm.lower() == 'y':
                stats = await cleaner.cleanup_orphaned_faiss_files()
                print(f"\n정리 완료: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            else:
                print("취소되었습니다.")
        
        elif choice == "5":
            print("👋 종료합니다.")
            break
        
        else:
            print("❌ 올바른 번호를 선택해주세요.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 사용자에 의해 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
