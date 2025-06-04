import os
import json
try:
    import numpy as np
except ImportError:
    print("numpy를 찾을 수 없습니다. 설치 중...")
    import subprocess
    subprocess.check_call(["pip", "install", "--no-cache-dir", "numpy==1.24.3"])
    import numpy as np

from sqlalchemy import select
from database import async_session, DocumentChunk
import asyncio

# 임베딩 모델이 없을 때 사용할 간단한 대체 클래스
class DummyEmbedder:
    def encode(self, texts):
        # 384차원의 랜덤 임베딩 생성
        return np.random.rand(len(texts), 384).astype('float32')

# 사용자별 임베딩 서비스
class UserEmbeddingService:
    """사용자별로 격리된 임베딩 서비스"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.dimension = 384  # 임베딩 차원
        
        # CloudType 환경 감지 및 파일 경로 설정
        self.is_cloudtype = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
        
        if self.is_cloudtype:
            # CloudType 환경: 임시 디렉토리 사용
            import tempfile
            temp_dir = tempfile.gettempdir()
            self.index_path = os.path.join(temp_dir, f"faiss_{user_id}.index")
            self.chunk_ids_path = os.path.join(temp_dir, f"faiss_{user_id}_chunks.json")
        else:
            # 로컬 환경: faiss_indexes 디렉토리 사용
            faiss_dir = "faiss_indexes"
            os.makedirs(faiss_dir, exist_ok=True)
            self.index_path = os.path.join(faiss_dir, f"{user_id}.index")
            self.chunk_ids_path = os.path.join(faiss_dir, f"{user_id}_chunks.json")
        
        # 필요한 모듈들은 메서드 내에서 필요할 때만 로드
        self._model = None
        self._faiss = None
        self.index = None
        self.chunk_ids = []
        
    def _load_faiss(self):
        """필요할 때만 FAISS 모듈 로드"""
        if self._faiss is None:
            try:
                print("FAISS 모듈 로딩 시작...")
                import faiss
                self._faiss = faiss
                # FAISS 인덱스 초기화 또는 로드
                print("FAISS 모듈 로드 완료, 인덱스 로딩 중...")
                self.load_index()
            except ImportError:
                print("FAISS 모듈 설치 필요. CloudType 환경에서는 직접 검색 구현 사용")
                # CloudType 환경에서는 간단한 검색 로직 사용
                self._faiss = None
    
    def _load_model(self):
        """필요할 때만 임베딩 모델 로드"""
        if self._model is None:
            try:
                print("임베딩 모델 로딩 시작...")
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer('paraphrase-MiniLM-L3-v2')
                print("임베딩 모델 로드 완료")
            except ImportError:
                print("SentenceTransformer 모듈 설치 필요. CloudType 환경에서는 간단한 임베딩 사용")
                # CloudType 환경에서는 간단한 임베딩 로직 사용
                self._model = None
    
    def load_index(self):
        """기존 FAISS 인덱스 로드 (CloudType 환경 대응)"""
        self._load_faiss()  # FAISS 모듈 로드
        
        try:
            if os.path.exists(self.index_path) and self._faiss:
                self.index = self._faiss.read_index(self.index_path)
                print(f"사용자 {self.user_id}: FAISS 인덱스 로드됨: {self.index.ntotal}개 벡터")
            else:
                if self._faiss:
                    self.index = self._faiss.IndexFlatIP(self.dimension)
                print(f"사용자 {self.user_id}: 새 FAISS 인덱스 생성")
            
            if os.path.exists(self.chunk_ids_path):
                with open(self.chunk_ids_path, 'r') as f:
                    self.chunk_ids = json.load(f)
                print(f"사용자 {self.user_id}: 청크 ID 로드됨: {len(self.chunk_ids)}개")
            else:
                self.chunk_ids = []
                
        except Exception as e:
            print(f"사용자 {self.user_id}: 인덱스 로드 실패: {e}")
            if self._faiss:
                self.index = self._faiss.IndexFlatIP(self.dimension)
            self.chunk_ids = []
    
    def save_index(self):
        """FAISS 인덱스 저장 (CloudType 환경 대응)"""
        if self.index is None:
            print("저장할 인덱스가 없습니다.")
            return
            
        self._load_faiss()  # FAISS 모듈 로드
        
        # CloudType 환경 감지
        import os
        IS_CLOUDTYPE = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
        
        if IS_CLOUDTYPE:
            # CloudType 환경: 임시 디렉토리 사용
            print(f"사용자 {self.user_id}: CloudType 환경 감지, 임시 디렉토리 사용")
            try:
                import tempfile
                # 임시 디렉토리에서 FAISS 인덱스 저장
                temp_dir = tempfile.gettempdir()
                temp_index_path = os.path.join(temp_dir, f"faiss_{self.user_id}.index")
                temp_chunk_ids_path = os.path.join(temp_dir, f"faiss_{self.user_id}_chunks.pkl")
                
                if self._faiss and self.index is not None:
                    self._faiss.write_index(self.index, temp_index_path)
                    print(f"사용자 {self.user_id}: FAISS 인덱스를 임시 디렉토리에 저장됨: {temp_index_path}")
                
                # 청크 ID 저장
                with open(temp_chunk_ids_path, 'w') as f:
                    json.dump(self.chunk_ids, f)
                print(f"사용자 {self.user_id}: 청크 ID 저장 완료: {temp_chunk_ids_path}")
                
                # 임시 경로를 실제 경로로 업데이트
                self.index_path = temp_index_path
                self.chunk_ids_path = temp_chunk_ids_path
                
            except Exception as e:
                print(f"사용자 {self.user_id}: CloudType 환경 FAISS 저장 실패: {e}")
                print(f"사용자 {self.user_id}: FAISS 저장 실패하지만 데이터베이스에는 임베딩이 저장됨")
        else:
            # 로컬 환경: 기존 방식 사용
            try:
                import fcntl
                import tempfile
                
                # 임시 파일로 저장 후 원자적 이동 (동시성 문제 해결)
                temp_index_path = self.index_path + ".tmp"
                temp_chunk_ids_path = self.chunk_ids_path + ".tmp"
                
                # FAISS 인덱스 저장
                if self._faiss and self.index is not None:
                    self._faiss.write_index(self.index, temp_index_path)
                
                # 청크 ID 저장
                with open(temp_chunk_ids_path, 'w') as f:
                    json.dump(self.chunk_ids, f)
                
                # 원자적으로 파일 이동 (다른 프로세스에서 읽는 도중 덮어쓰기 방지)
                try:
                    os.rename(temp_index_path, self.index_path)
                    os.rename(temp_chunk_ids_path, self.chunk_ids_path)
                    print(f"사용자 {self.user_id}: FAISS 인덱스 저장 완료")
                except OSError as rename_err:
                    print(f"사용자 {self.user_id}: 파일 이동 실패: {rename_err}")
                    # 임시 파일 정리
                    if os.path.exists(temp_index_path):
                        os.remove(temp_index_path)
                    if os.path.exists(temp_chunk_ids_path):
                        os.remove(temp_chunk_ids_path)
                    raise
                    
            except ImportError:
                # fcntl이 없는 환경 (Windows 등)에서는 기본 저장 방식 사용
                try:
                    if self._faiss and self.index is not None:
                        self._faiss.write_index(self.index, self.index_path)
                    with open(self.chunk_ids_path, 'w') as f:
                        json.dump(self.chunk_ids, f)
                    print(f"사용자 {self.user_id}: FAISS 인덱스 저장 완료 (기본 방식)")
                except Exception as basic_err:
                    print(f"사용자 {self.user_id}: 기본 저장 방식 실패: {basic_err}")
            except Exception as e:
                print(f"사용자 {self.user_id}: 인덱스 저장 실패: {e}")
    
    def create_embedding(self, text):
        """텍스트를 임베딩으로 변환"""
        try:
            self._load_model()  # 임베딩 모델 로드
            self._load_faiss()  # FAISS 모듈 로드
            
            # 모델이 로드되지 않았다면 대체 임베딩 사용
            if self._model is None:
                print("모델 로드 실패, 대체 임베딩 사용")
                dummy_embedder = DummyEmbedder()
                embedding = dummy_embedder.encode([text])
                return embedding[0]
            
            embedding = self._model.encode([text])
            # L2 정규화 (코사인 유사도를 위해)
            if self._faiss:
                try:
                    self._faiss.normalize_L2(embedding.astype('float32'))
                except Exception as norm_err:
                    print(f"L2 정규화 실패: {norm_err}")
            return embedding[0]
        except Exception as e:
            print(f"임베딩 생성 실패: {e}")
            import traceback
            print(traceback.format_exc())
            
            # 오류 발생 시 임의 임베딩 반환
            print("오류 발생, 대체 임베딩 사용")
            return np.random.rand(self.dimension).astype('float32')
    
    def add_to_index(self, chunk_id, text):
        """FAISS 인덱스에 텍스트 추가"""
        try:
            self._load_faiss()  # FAISS 모듈 로드
            
            # FAISS 모듈을 로드할 수 없는 경우
            if self._faiss is None:
                print("FAISS 모듈을 로드할 수 없음, 대체 임베딩만 생성")
                try:
                    # 임베딩만 생성 (인덱스에는 추가하지 않음)
                    embedding = self.create_embedding(text)
                    print(f"인덱스 없이 임베딩만 생성: chunk_id={chunk_id}")
                    
                    # 청크 ID 추가 (인덱스 없이)
                    self.chunk_ids.append(chunk_id)
                    return embedding.tolist()
                except Exception as embed_err:
                    print(f"대체 임베딩 생성 실패: {embed_err}")
                    return None
            
            # 정상적인 경우
            embedding = self.create_embedding(text)
            
            # FAISS 인덱스에 추가
            if self.index is None:
                print("인덱스 초기화 중...")
                self.index = self._faiss.IndexFlatIP(self.dimension)
            
            try:    
                self.index.add(embedding.reshape(1, -1).astype('float32'))
                self.chunk_ids.append(chunk_id)
                
                print(f"인덱스에 추가됨: chunk_id={chunk_id}")
                return embedding.tolist()
            except Exception as idx_err:
                print(f"인덱스 추가 중 오류: {idx_err}")
                import traceback
                print(traceback.format_exc())
                
                # 인덱스 추가 실패해도 임베딩은 반환
                self.chunk_ids.append(chunk_id)
                return embedding.tolist()
                
        except Exception as e:
            print(f"인덱스 추가 실패: {e}")
            import traceback
            print(traceback.format_exc())
            return None
    
    async def search_similar(self, query, k=5):
        """유사한 문서 청크 검색 (사용자별 격리)"""
        try:
            self._load_faiss()  # FAISS 모듈 로드
            
            # FAISS 모듈을 로드할 수 없거나 인덱스가 비어있는 경우
            if self._faiss is None or self.index is None or self.index.ntotal == 0:
                print(f"사용자 {self.user_id}: FAISS 인덱스가 없거나 비어있음, 대체 검색 로직 사용")
                # 대체 검색 로직 (간단한 키워드 매칭)
                return await self._fallback_search(query, k)
            
            # 쿼리 임베딩 생성
            try:
                query_embedding = self.create_embedding(query)
            except Exception as embed_err:
                print(f"사용자 {self.user_id}: 쿼리 임베딩 생성 실패: {embed_err}")
                return await self._fallback_search(query, k)
            
            # FAISS에서 검색
            try:
                scores, indices = self.index.search(
                    query_embedding.reshape(1, -1).astype('float32'), 
                    min(k, self.index.ntotal)
                )
            except Exception as search_err:
                print(f"사용자 {self.user_id}: FAISS 검색 오류: {search_err}")
                return await self._fallback_search(query, k)
            
            # 결과 처리 (사용자별 필터링)
            results = []
            try:
                async with async_session() as session:
                    for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                        if idx >= 0 and idx < len(self.chunk_ids):
                            chunk_id = self.chunk_ids[idx]
                            
                            # 데이터베이스에서 청크 정보 조회 (사용자 ID로 필터링)
                            try:
                                stmt = select(DocumentChunk).where(
                                    DocumentChunk.id == chunk_id,
                                    DocumentChunk.user_id == self.user_id  # 사용자별 필터링
                                )
                                result = await session.execute(stmt)
                                chunk = result.scalar_one_or_none()
                                
                                if chunk:
                                    results.append({
                                        'chunk_id': chunk_id,
                                        'text': chunk.chunk_text,
                                        'score': float(score),
                                        'document_id': chunk.document_id,
                                        'user_id': chunk.user_id
                                    })
                            except Exception as db_err:
                                print(f"사용자 {self.user_id}: 청크 ID {chunk_id} 조회 실패: {db_err}")
                
                return results
            except Exception as result_err:
                print(f"사용자 {self.user_id}: 결과 처리 오류: {result_err}")
                return []
                
        except Exception as e:
            print(f"사용자 {self.user_id}: 검색 실패: {e}")
            import traceback
            print(traceback.format_exc())
            return []
    
    async def _fallback_search(self, query, k=5):
        """FAISS가 없을 때 대체 검색 로직 (사용자별 격리)"""
        print(f"사용자 {self.user_id}: 대체 검색 로직 사용 중...")
        results = []
        
        try:
            # CloudType 환경 감지
            import os
            IS_CLOUDTYPE = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
            
            if IS_CLOUDTYPE:
                print(f"사용자 {self.user_id}: CloudType 환경: 데이터베이스 연결 건너뜀, 더미 결과 반환")
                # CloudType 환경에서는 더미 응답 반환
                return [{
                    'chunk_id': 1,
                    'text': f"사용자 {self.user_id}의 CloudType 환경에서 '{query}'에 대한 기본 응답입니다. 현재 데이터베이스 연결에 문제가 있어 저장된 문서를 검색할 수 없습니다.",
                    'score': 0.5,
                    'document_id': 1,
                    'user_id': self.user_id
                }]
            
            # 로컬 환경에서만 실제 데이터베이스 검색 수행 (사용자별 필터링)
            async with async_session() as session:
                # 단순 키워드 매칭으로 검색 (사용자별 필터링)
                query_terms = set(query.lower().split())
                
                # 해당 사용자의 최근 문서 청크 가져오기
                stmt = select(DocumentChunk).where(
                    DocumentChunk.user_id == self.user_id
                ).order_by(DocumentChunk.id.desc()).limit(100)
                result = await session.execute(stmt)
                chunks = result.scalars().all()
                
                # 각 청크와 쿼리의 유사도 계산 (간단한 용어 중복)
                scored_chunks = []
                for chunk in chunks:
                    chunk_terms = set(chunk.chunk_text.lower().split())
                    common_terms = query_terms.intersection(chunk_terms)
                    if common_terms:
                        score = len(common_terms) / len(query_terms)
                        scored_chunks.append((chunk, score))
                
                # 점수로 정렬하고 상위 k개 반환
                scored_chunks.sort(key=lambda x: x[1], reverse=True)
                for chunk, score in scored_chunks[:k]:
                    results.append({
                        'chunk_id': chunk.id,
                        'text': chunk.chunk_text,
                        'score': score,
                        'document_id': chunk.document_id,
                        'user_id': chunk.user_id
                    })
                    
            return results
        except Exception as e:
            print(f"사용자 {self.user_id}: 대체 검색 실패: {e}")
            import traceback
            print(traceback.format_exc())
            return []

# 사용자별 임베딩 서비스 팩토리
class EmbeddingServiceManager:
    """사용자별 임베딩 서비스 관리자"""
    
    def __init__(self):
        self._services = {}  # user_id -> UserEmbeddingService
        self._max_services = 50  # 메모리 절약을 위한 최대 서비스 수 (100에서 50으로 감소)
        self._access_count = {}  # user_id -> access count (LRU 구현용)
        self._lock = None  # 동시성 보호용 락 (필요시 생성)
    
    def _get_lock(self):
        """필요시 락 생성 (지연 초기화)"""
        if self._lock is None:
            try:
                import asyncio
                self._lock = asyncio.Lock()
            except Exception:
                # asyncio가 없는 환경에서는 None으로 유지
                pass
        return self._lock
    
    async def get_service(self, user_id: str) -> UserEmbeddingService:
        """사용자별 임베딩 서비스 인스턴스 반환 (동시성 보호)"""
        lock = self._get_lock()
        
        if lock:
            async with lock:
                return self._get_service_sync(user_id)
        else:
            return self._get_service_sync(user_id)
    
    def _get_service_sync(self, user_id: str) -> UserEmbeddingService:
        """동기적 서비스 획득 (락 내부에서 호출)"""
        if user_id not in self._services:
            # 메모리 관리: 최대 서비스 수 초과 시 가장 적게 사용된 것 제거
            if len(self._services) >= self._max_services:
                # LRU (Least Recently Used) 방식으로 제거
                if self._access_count:
                    lru_user = min(self._access_count.items(), key=lambda x: x[1])[0]
                else:
                    # access_count가 비어있으면 첫 번째 제거
                    lru_user = next(iter(self._services))
                
                old_service = self._services.pop(lru_user)
                self._access_count.pop(lru_user, None)
                
                # 인덱스 저장
                try:
                    old_service.save_index()
                    print(f"사용자 {lru_user} 서비스 정리 및 인덱스 저장 완료")
                except Exception as e:
                    print(f"사용자 {lru_user} 인덱스 저장 실패: {e}")
            
            # 새 서비스 생성
            self._services[user_id] = UserEmbeddingService(user_id)
            self._access_count[user_id] = 0
        
        # 접근 횟수 증가
        self._access_count[user_id] = self._access_count.get(user_id, 0) + 1
        return self._services[user_id]
    
    async def cleanup_service(self, user_id: str):
        """특정 사용자의 서비스 정리 (동시성 보호)"""
        lock = self._get_lock()
        
        if lock:
            async with lock:
                self._cleanup_service_sync(user_id)
        else:
            self._cleanup_service_sync(user_id)
    
    def _cleanup_service_sync(self, user_id: str):
        """동기적 서비스 정리 (락 내부에서 호출)"""
        if user_id in self._services:
            service = self._services.pop(user_id)
            self._access_count.pop(user_id, None)
            try:
                service.save_index()
                print(f"사용자 {user_id} 서비스 정리 완료")
            except Exception as e:
                print(f"사용자 {user_id} 서비스 정리 중 오류: {e}")
    
    def get_stats(self):
        """서비스 매니저 통계 반환"""
        return {
            "active_services": len(self._services),
            "max_services": self._max_services,
            "users": list(self._services.keys()),
            "access_counts": dict(self._access_count)
        }

# 전역 임베딩 서비스 매니저
embedding_manager = EmbeddingServiceManager()

# 하위 호환성을 위한 래퍼 함수들
async def get_embedding_service(user_id: str = "default") -> UserEmbeddingService:
    """사용자별 임베딩 서비스 반환"""
    return await embedding_manager.get_service(user_id)
