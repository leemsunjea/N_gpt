import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from database import async_session, DocumentChunk
import asyncio

class EmbeddingService:
    def __init__(self):
        # 임베딩 모델 초기화 - 더 작은 모델 사용
        self.model = SentenceTransformer('paraphrase-MiniLM-L3-v2')  # 더 작은 모델로 변경
        self.dimension = 384  # 임베딩 차원
        
        # FAISS 인덱스 초기화
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product (코사인 유사도)
        
        # 인덱스 파일 경로
        self.index_path = "static/faiss_index.bin"
        self.chunk_ids_path = "static/chunk_ids.json"
        
        # 기존 인덱스 로드
        self.chunk_ids = []
        self.load_index()
    
    def load_index(self):
        """기존 FAISS 인덱스 로드"""
        try:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                print(f"FAISS 인덱스 로드됨: {self.index.ntotal}개 벡터")
            
            if os.path.exists(self.chunk_ids_path):
                with open(self.chunk_ids_path, 'r') as f:
                    self.chunk_ids = json.load(f)
                print(f"청크 ID 로드됨: {len(self.chunk_ids)}개")
        except Exception as e:
            print(f"인덱스 로드 실패: {e}")
            self.index = faiss.IndexFlatIP(self.dimension)
            self.chunk_ids = []
    
    def save_index(self):
        """FAISS 인덱스 저장"""
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.chunk_ids_path, 'w') as f:
                json.dump(self.chunk_ids, f)
            print("FAISS 인덱스 저장 완료")
        except Exception as e:
            print(f"인덱스 저장 실패: {e}")
    
    def create_embedding(self, text):
        """텍스트를 임베딩으로 변환"""
        embedding = self.model.encode([text])
        # L2 정규화 (코사인 유사도를 위해)
        faiss.normalize_L2(embedding.astype('float32'))
        return embedding[0]
    
    def add_to_index(self, chunk_id, text):
        """FAISS 인덱스에 텍스트 추가"""
        try:
            embedding = self.create_embedding(text)
            
            # FAISS 인덱스에 추가
            self.index.add(embedding.reshape(1, -1).astype('float32'))
            self.chunk_ids.append(chunk_id)
            
            print(f"인덱스에 추가됨: chunk_id={chunk_id}")
            return embedding.tolist()
        except Exception as e:
            print(f"인덱스 추가 실패: {e}")
            return None
    
    async def search_similar(self, query, k=5):
        """유사한 문서 청크 검색"""
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
embedding_service = EmbeddingService()
