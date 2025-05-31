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

# 더 가벼운 임베딩 서비스
class LightweightEmbeddingService:
    def __init__(self):
        # 인덱스 파일 경로
        self.index_path = "faiss_index.bin"
        self.chunk_ids_path = "chunk_ids.json"
        self.dimension = 384  # 임베딩 차원
        
        # 필요한 모듈들은 메서드 내에서 필요할 때만 로드
        self._model = None
        self._faiss = None
        self.index = None
        self.chunk_ids = []
        
        # 환경 변수 확인 - CloudType 배포 여부
        self.is_cloudtype = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
        
        # 환경 변수 확인 - CloudType 배포 여부
        self.is_cloudtype = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
        
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
        """기존 FAISS 인덱스 로드"""
        self._load_faiss()  # FAISS 모듈 로드
        
        try:
            if os.path.exists(self.index_path):
                self.index = self._faiss.read_index(self.index_path)
                print(f"FAISS 인덱스 로드됨: {self.index.ntotal}개 벡터")
            else:
                self.index = self._faiss.IndexFlatIP(self.dimension)
            
            if os.path.exists(self.chunk_ids_path):
                with open(self.chunk_ids_path, 'r') as f:
                    self.chunk_ids = json.load(f)
                print(f"청크 ID 로드됨: {len(self.chunk_ids)}개")
        except Exception as e:
            print(f"인덱스 로드 실패: {e}")
            self.index = self._faiss.IndexFlatIP(self.dimension)
            self.chunk_ids = []
    
    def save_index(self):
        """FAISS 인덱스 저장"""
        if self.index is None:
            print("저장할 인덱스가 없습니다.")
            return
            
        self._load_faiss()  # FAISS 모듈 로드
        
        try:
            self._faiss.write_index(self.index, self.index_path)
            with open(self.chunk_ids_path, 'w') as f:
                json.dump(self.chunk_ids, f)
            print("FAISS 인덱스 저장 완료")
        except Exception as e:
            print(f"인덱스 저장 실패: {e}")
    
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
        """유사한 문서 청크 검색"""
        try:
            self._load_faiss()  # FAISS 모듈 로드
            
            # FAISS 모듈을 로드할 수 없거나 인덱스가 비어있는 경우
            if self._faiss is None or self.index is None or self.index.ntotal == 0:
                print("FAISS 인덱스가 없거나 비어있음, 대체 검색 로직 사용")
                # 대체 검색 로직 (간단한 키워드 매칭)
                return await self._fallback_search(query, k)
            
            # 쿼리 임베딩 생성
            try:
                query_embedding = self.create_embedding(query)
            except Exception as embed_err:
                print(f"쿼리 임베딩 생성 실패: {embed_err}")
                return await self._fallback_search(query, k)
            
            # FAISS에서 검색
            try:
                scores, indices = self.index.search(
                    query_embedding.reshape(1, -1).astype('float32'), 
                    min(k, self.index.ntotal)
                )
            except Exception as search_err:
                print(f"FAISS 검색 오류: {search_err}")
                return await self._fallback_search(query, k)
            
            # 결과 처리
            results = []
            try:
                async with async_session() as session:
                    for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                        if idx >= 0 and idx < len(self.chunk_ids):
                            chunk_id = self.chunk_ids[idx]
                            
                            # 데이터베이스에서 청크 정보 조회
                            try:
                                stmt = select(DocumentChunk).where(DocumentChunk.id == chunk_id)
                                result = await session.execute(stmt)
                                chunk = result.scalar_one_or_none()
                                
                                if chunk:
                                    results.append({
                                        'chunk_id': chunk_id,
                                        'text': chunk.chunk_text,
                                        'score': float(score),
                                        'document_id': chunk.document_id
                                    })
                            except Exception as db_err:
                                print(f"청크 ID {chunk_id} 조회 실패: {db_err}")
                
                return results
            except Exception as result_err:
                print(f"결과 처리 오류: {result_err}")
                return []
                
        except Exception as e:
            print(f"검색 실패: {e}")
            import traceback
            print(traceback.format_exc())
            return []
    
    async def _fallback_search(self, query, k=5):
        """FAISS가 없을 때 대체 검색 로직"""
        print("대체 검색 로직 사용 중...")
        results = []
        
        try:
            # 단순 키워드 매칭으로 검색
            query_terms = set(query.lower().split())
            
            async with async_session() as session:
                # 최근 문서 청크 가져오기
                stmt = select(DocumentChunk).order_by(DocumentChunk.id.desc()).limit(100)
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
                        'document_id': chunk.document_id
                    })
                    
            return results
        except Exception as e:
            print(f"대체 검색 실패: {e}")
            import traceback
            print(traceback.format_exc())
            return []

# 전역 임베딩 서비스 인스턴스
embedding_service = LightweightEmbeddingService()
