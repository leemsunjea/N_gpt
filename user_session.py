import uuid
import hashlib
from fastapi import Request, Cookie, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from database import User, async_session
from datetime import datetime, timedelta
import os

class UserSessionManager:
    """사용자 세션 관리자"""
    
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # 24시간 세션 유지
    
    def generate_user_id(self, request: Request) -> str:
        """클라이언트 기반으로 고유한 사용자 ID 생성"""
        # IP 주소, 사용자 에이전트를 조합하여 사용자 식별
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # 추가 헤더 정보로 더 고유한 식별자 생성
        accept_language = request.headers.get("accept-language", "")
        accept_encoding = request.headers.get("accept-encoding", "")
        
        # 해시를 통해 고유 ID 생성 (더 많은 정보 포함)
        unique_string = f"{client_ip}_{user_agent}_{accept_language}_{accept_encoding}"
        user_id = hashlib.sha256(unique_string.encode()).hexdigest()[:16]
        
        # 사용자 ID 앞에 접두사 추가 (더 쉬운 식별을 위해)
        return f"user_{user_id}"
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # Proxy 환경을 고려한 IP 추출
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(',')[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def get_or_create_user(self, request: Request, user_id_cookie: str = None) -> str:
        """사용자 ID를 가져오거나 새로 생성"""
        try:
            # 쿠키에서 user_id 확인
            if user_id_cookie:
                # 데이터베이스에서 사용자 확인
                async with async_session() as session:
                    stmt = select(User).where(User.id == user_id_cookie)
                    result = await session.execute(stmt)
                    user = result.scalar_one_or_none()
                    
                    if user:
                        # 마지막 활동 시간 업데이트
                        user.last_active = datetime.utcnow()
                        await session.commit()
                        return user_id_cookie
            
            # 새 사용자 ID 생성
            user_id = self.generate_user_id(request)
            
            # 데이터베이스에 사용자 생성
            async with async_session() as session:
                # 기존 사용자 확인
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                existing_user = result.scalar_one_or_none()
                
                if not existing_user:
                    new_user = User(
                        id=user_id,
                        created_at=datetime.utcnow(),
                        last_active=datetime.utcnow()
                    )
                    session.add(new_user)
                    await session.commit()
                    print(f"새 사용자 생성: {user_id}")
                else:
                    # 기존 사용자의 마지막 활동 시간 업데이트
                    existing_user.last_active = datetime.utcnow()
                    await session.commit()
                    print(f"기존 사용자 활동 업데이트: {user_id}")
            
            return user_id
            
        except Exception as e:
            print(f"사용자 세션 관리 오류: {e}")
            import traceback
            print(traceback.format_exc())
            # 오류 발생 시 임시 사용자 ID 반환
            return f"temp_{uuid.uuid4().hex[:8]}"
    
    async def cleanup_old_sessions(self):
        """오래된 세션 정리 (연관 데이터 포함)"""
        try:
            cutoff_time = datetime.utcnow() - self.session_timeout
            
            async with async_session() as session:
                # 오래된 사용자들 조회
                from database import Document, DocumentChunk
                
                stmt = select(User).where(User.last_active < cutoff_time)
                result = await session.execute(stmt)
                old_users = result.scalars().all()
                
                for user in old_users:
                    print(f"오래된 사용자 데이터 정리: {user.id}")
                    
                    # 사용자의 문서 청크 삭제
                    chunk_stmt = select(DocumentChunk).where(DocumentChunk.user_id == user.id)
                    chunk_result = await session.execute(chunk_stmt)
                    chunks = chunk_result.scalars().all()
                    
                    for chunk in chunks:
                        await session.delete(chunk)
                    
                    # 사용자의 문서 삭제
                    doc_stmt = select(Document).where(Document.user_id == user.id)
                    doc_result = await session.execute(doc_stmt)
                    documents = doc_result.scalars().all()
                    
                    for document in documents:
                        await session.delete(document)
                    
                    # 사용자 레코드 삭제
                    await session.delete(user)
                    
                    print(f"사용자 {user.id}: {len(documents)}개 문서, {len(chunks)}개 청크 정리됨")
                
                await session.commit()
                print(f"{len(old_users)}개의 오래된 세션 및 연관 데이터 정리 완료")
                
        except Exception as e:
            print(f"세션 정리 오류: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def cleanup_expired_sessions(self, days_threshold: int = 7) -> dict:
        """만료된 세션 데이터 정리"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        stats = {
            "deleted_users": 0,
            "errors": []
        }
        
        try:
            async with async_session() as session:
                # 오래된 사용자 세션 삭제
                result = await session.execute(
                    delete(User).where(User.last_active < cutoff_date)
                )
                stats["deleted_users"] = result.rowcount
                await session.commit()
                
        except Exception as e:
            stats["errors"].append(f"세션 정리 실패: {e}")
        
        return stats
    
    async def get_session_stats(self) -> dict:
        """세션 통계 조회"""
        try:
            async with async_session() as session:
                # 전체 사용자 수
                total_result = await session.execute(
                    select(func.count(User.id))
                )
                total_users = total_result.scalar()
                
                # 활성 사용자 수 (24시간 내)
                active_cutoff = datetime.now() - timedelta(hours=24)
                active_result = await session.execute(
                    select(func.count(User.id)).where(User.last_active > active_cutoff)
                )
                active_users = active_result.scalar()
                
                # 최근 사용자 목록
                recent_result = await session.execute(
                    select(User).order_by(User.last_active.desc()).limit(10)
                )
                recent_users = recent_result.scalars().all()
                
                return {
                    "total_users": total_users,
                    "active_users_24h": active_users,
                    "recent_users": [
                        {
                            "user_id": user.user_id,
                            "last_active": user.last_active.isoformat() if user.last_active else None,
                            "created_at": user.created_at.isoformat() if user.created_at else None
                        }
                        for user in recent_users
                    ]
                }
                
        except Exception as e:
            return {"error": f"통계 조회 실패: {e}"}

# 전역 세션 매니저 인스턴스
session_manager = UserSessionManager()

# FastAPI 의존성 함수
async def get_current_user_id(request: Request, user_id: str = Cookie(None)) -> str:
    """현재 사용자 ID를 가져오는 의존성 함수"""
    return await session_manager.get_or_create_user(request, user_id)

def set_user_cookie(response: Response, user_id: str):
    """응답에 사용자 쿠키 설정"""
    response.set_cookie(
        key="user_id",
        value=user_id,
        max_age=86400 * 7,  # 7일
        httponly=True,
        secure=False,  # HTTPS가 아닌 환경에서도 작동하도록
        samesite="lax"
    )
