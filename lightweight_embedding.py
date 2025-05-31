import os
import json
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
        self._load_model()  # 임베딩 모델 로드
        self._load_faiss()  # FAISS 모듈 로드
        
        embedding = self._model.encode([text])
        # L2 정규화 (코사인 유사도를 위해)
        self._faiss.normalize_L2(embedding.astype('float32'))
        return embedding[0]
    
    def add_to_index(self, chunk_id, text):
        """FAISS 인덱스에 텍스트 추가"""
        self._load_faiss()  # FAISS 모듈 로드
        
        try:
            embedding = self.create_embedding(text)
            
            # FAISS 인덱스에 추가
            if self.index is None:
                self.index = self._faiss.IndexFlatIP(self.dimension)
                
            self.index.add(embedding.reshape(1, -1).astype('float32'))
            self.chunk_ids.append(chunk_id)
            
            print(f"인덱스에 추가됨: chunk_id={chunk_id}")
            return embedding.tolist()
        except Exception as e:
            print(f"인덱스 추가 실패: {e}")
            return None
    
    async def search_similar(self, query, k=5):
        """유사한 문서 청크 검색"""
        self._load_faiss()  # FAISS 모듈 로드
        
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.create_embedding(query)
            
            # FAISS에서 검색
            scores, indices = self.index.search(
                query_embedding.reshape(1, -1).astype('float32'), k
            )
            
            # 결과 처리
            results = []
            async with async_session() as session:
                for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                    if idx >= 0 and idx < len(self.chunk_ids):
                        chunk_id = self.chunk_ids[idx]
                        
                        # 데이터베이스에서 청크 정보 조회
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
            
            return results
        except Exception as e:
            print(f"검색 실패: {e}")
            return []

# 전역 임베딩 서비스 인스턴스
embedding_service = LightweightEmbeddingService()
