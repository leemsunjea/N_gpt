from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import os
# uvicorn은 조건부 import (CloudType 환경에서는 전역 설치)
try:
    import uvicorn
except ImportError:
    uvicorn = None
import traceback

from database import get_db, create_tables, Document, DocumentChunk
from document_processor import DocumentProcessor
# 경량 임베딩 서비스 사용
from lightweight_embedding import embedding_service
from chat_service import chat_service
import re
import unicodedata

# PostgreSQL 호환 텍스트 정제 함수들
def clean_for_postgresql(text):
    """PostgreSQL에 안전하게 저장할 수 있도록 텍스트를 정제합니다."""
    if not text:
        return ""
    
    # 1. null 바이트 제거
    text = text.replace('\x00', '')
    
    # 2. 대체 문자 제거
    text = text.replace('\ufffd', '')
    
    # 3. 기타 제어 문자 제거 (탭, 개행, 캐리지 리턴은 유지)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    # 4. Unicode 정규화 (NFD -> NFC)
    text = unicodedata.normalize('NFC', text)
    
    # 5. 비인쇄 가능한 Unicode 문자 제거
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\t\n\r')
    
    # 6. 연속된 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    # 7. 앞뒤 공백 제거
    text = text.strip()
    
    return text

def validate_utf8(text):
    """UTF-8 인코딩이 유효한지 확인합니다."""
    try:
        text.encode('utf-8').decode('utf-8')
        return True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False

def safe_truncate(text, max_length=1000000):
    """텍스트를 안전하게 자릅니다. (UTF-8 문자 경계 고려)"""
    if len(text.encode('utf-8')) <= max_length:
        return text
    
    # 바이트 단위로 자르되, 문자 경계를 고려
    encoded = text.encode('utf-8')
    truncated = encoded[:max_length]
    
    # 불완전한 UTF-8 시퀀스 제거
    while truncated and truncated[-1] & 0x80:
        if truncated[-1] & 0x40:
            break
        truncated = truncated[:-1]
    
    try:
        return truncated.decode('utf-8')
    except UnicodeDecodeError:
        # 안전하게 처리
        return truncated.decode('utf-8', errors='ignore')

import re
import unicodedata

class TextCleaner:
    """PostgreSQL과 호환되는 텍스트 정제 유틸리티"""
    
    @staticmethod
    def clean_for_postgresql(text):
        """PostgreSQL에 안전하게 저장할 수 있도록 텍스트를 정제합니다."""
        if not text:
            return ""
        
        # 1. null 바이트 제거
        text = text.replace('\x00', '')
        
        # 2. 대체 문자 제거
        text = text.replace('\ufffd', '')
        
        # 3. 기타 제어 문자 제거 (탭, 개행, 캐리지 리턴은 유지)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 4. Unicode 정규화 (NFD -> NFC)
        text = unicodedata.normalize('NFC', text)
        
        # 5. 비인쇄 가능한 Unicode 문자 제거
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\t\n\r')
        
        # 6. 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        
        # 7. 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    @staticmethod
    def validate_utf8(text):
        """UTF-8 인코딩이 유효한지 확인합니다."""
        try:
            text.encode('utf-8').decode('utf-8')
            return True
        except (UnicodeEncodeError, UnicodeDecodeError):
            return False
    
    @staticmethod
    def safe_truncate(text, max_length=1000000):
        """텍스트를 안전하게 자릅니다. (UTF-8 문자 경계 고려)"""
        if len(text.encode('utf-8')) <= max_length:
            return text
        
        # 바이트 단위로 자르되, 문자 경계를 고려
        encoded = text.encode('utf-8')
        truncated = encoded[:max_length]
        
        # 불완전한 UTF-8 시퀀스 제거
        while truncated and truncated[-1] & 0x80:
            if truncated[-1] & 0x40:
                break
            truncated = truncated[:-1]
        
        try:
            return truncated.decode('utf-8')
        except UnicodeDecodeError:
            # 안전하게 처리
            return truncated.decode('utf-8', errors='ignore')

app = FastAPI(title="N_GPT Document Search", version="1.0.0")

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    import os
    # 서버 시작 시 DB 초기화: 모든 테이블 삭제 후 재생성
    from database import engine, Base
    print("서버 시작 시 DB 초기화 중...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("DB 초기화 완료: 모든 테이블이 재생성되었습니다.")

    # 필요한 디렉토리 생성 시도 (권한 문제가 있을 수 있음)
    try:
        os.makedirs("static", exist_ok=True)
        os.makedirs("templates", exist_ok=True)
        print("필요한 디렉토리 생성 완료")
    except PermissionError:
        print("디렉토리 생성 권한이 없습니다. 기존 디렉토리를 사용합니다.")
    
    # favicon.ico 파일 확인 - 권한 문제를 피하기 위해 실제로 생성하지 않음
    favicon_path = "static/favicon.ico"
    if not os.path.exists(favicon_path):
        print(f"{favicon_path} 파일이 없습니다. CloudType 환경에서는 이 파일을 직접 생성할 수 없습니다.")
        print("파비콘 요청은 무시됩니다.")
    
    # 템플릿 파일 확인 - 권한 문제가 있을 수 있으므로 파일 생성을 시도하지 않음
    template_path = "templates/index.html"
    if not os.path.exists(template_path):
        print(f"{template_path} 파일이 없습니다. CloudType 환경에서는 파일을 직접 생성할 수 없습니다.")
    
    # 정적 파일 확인
    css_path = "static/style.css"
    if not os.path.exists(css_path):
        print(f"{css_path} 파일이 없어 기본 스타일을 생성합니다.")
        try:
            with open(css_path, "w", encoding="utf-8") as f:
                f.write("body { font-family: Arial, sans-serif; }")
        except Exception as css_err:
            print(f"CSS 파일 생성 실패: {css_err}")
        
    # 모든 환경에서 테이블 생성 시도
    try:
        print("데이터베이스 테이블 생성 시도...")
        await create_tables()
        print("데이터베이스 테이블 생성 완료")
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        import traceback
        print(traceback.format_exc())
        # 환경 변수 강제 설정으로 CloudType 환경 인식
        os.environ['CLOUDTYPE_DEPLOYMENT'] = '1'
        print("외부 데이터베이스 사용 모드로 전환")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """메인 페이지"""
    return HTMLResponse(content=open("templates/index.html", "r", encoding="utf-8").read())

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """문서 업로드 및 임베딩"""
    try:
        print(f"문서 업로드 시작: {file.filename}")
        print(f"환경: CloudType={os.environ.get('CLOUDTYPE_DEPLOYMENT', '0')}")
        print(f"데이터베이스 URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        
        # 파일 내용 읽기 시도
        try:
            file_content = await file.read()
            print(f"파일 크기: {len(file_content)} 바이트")
        except Exception as file_err:
            print(f"파일 읽기 오류: {str(file_err)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"파일 읽기 실패: {str(file_err)}")
        
        # 텍스트 추출 시도
        try:
            text_content = DocumentProcessor.extract_text(file.filename, file_content)
            print(f"추출된 텍스트 크기: {len(text_content) if text_content else 0} 자")
        except Exception as extract_err:
            print(f"텍스트 추출 오류: {str(extract_err)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"텍스트 추출 실패: {str(extract_err)}")
        
        if not text_content:
            print("추출된 텍스트가 없습니다.")
            raise HTTPException(status_code=400, detail="텍스트를 추출할 수 없습니다.")
        
        # 데이터베이스 연결 테스트
        try:
            await db.connection()
            print("데이터베이스 연결 성공")
        except Exception as conn_err:
            print(f"데이터베이스 연결 테스트 실패: {str(conn_err)}")
            import traceback
            print(traceback.format_exc())
        
        # 문서 저장 시도
        try:
            print("문서 저장 시작...")
            # PostgreSQL 호환성을 위한 강력한 텍스트 정제
            clean_text = clean_for_postgresql(text_content)
            
            # UTF-8 유효성 검증
            if not validate_utf8(clean_text):
                print("UTF-8 인코딩 오류 감지, 강제 정제 중...")
                clean_text = clean_text.encode('utf-8', errors='ignore').decode('utf-8')
            
            # 안전한 텍스트 길이 제한
            clean_text = safe_truncate(clean_text, 1000000)  # 1MB 제한
            if len(clean_text) != len(text_content):
                print(f"텍스트 정제 및 길이 조정: {len(text_content)} -> {len(clean_text)}")
            
            # 최종 검증: NULL 바이트가 완전히 제거되었는지 확인
            if '\x00' in clean_text:
                print("경고: NULL 바이트가 여전히 존재함, 강제 제거 중...")
                clean_text = clean_text.replace('\x00', '')
            
            document = Document(
                filename=file.filename,
                content=clean_text
            )
            db.add(document)
            await db.flush()  # ID 생성을 위해
            print(f"문서 ID 생성: {document.id}")
        except Exception as doc_err:
            print(f"문서 저장 오류: {str(doc_err)}")
            import traceback
            print(traceback.format_exc())
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"문서 저장 실패: {str(doc_err)}")
        
        # 텍스트 청킹
        try:
            chunks = DocumentProcessor.chunk_text(clean_text)
            print(f"텍스트 청킹 완료: {len(chunks)}개 청크 생성")
        except Exception as chunk_err:
            print(f"텍스트 청킹 오류: {str(chunk_err)}")
            import traceback
            print(traceback.format_exc())
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"텍스트 청킹 실패: {str(chunk_err)}")
        
        # 각 청크를 임베딩하고 저장
        chunk_count = 0
        try:
            for i, chunk_text in enumerate(chunks):
                print(f"청크 {i+1}/{len(chunks)} 처리 중...")
                
                # 청크 텍스트도 PostgreSQL 호환성을 위해 정제
                clean_chunk_text = clean_for_postgresql(chunk_text)
                if '\x00' in clean_chunk_text:
                    print(f"청크 {i+1}에서 NULL 바이트 제거 중...")
                    clean_chunk_text = clean_chunk_text.replace('\x00', '')
                
                # 데이터베이스에 청크 저장
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_text=clean_chunk_text,
                    chunk_index=i
                )
                db.add(chunk)
                await db.flush()
                
                # FAISS 인덱스에 추가
                print(f"청크 {i+1} 임베딩 생성 중...")
                try:
                    embedding = embedding_service.add_to_index(chunk.id, clean_chunk_text)
                    
                    # 임베딩을 데이터베이스에 저장
                    if embedding:
                        chunk.embedding = json.dumps(embedding)
                        print(f"청크 {i+1} 임베딩 저장 완료")
                    else:
                        print(f"청크 {i+1} 임베딩 생성 실패")
                except Exception as embed_err:
                    print(f"청크 {i+1} 임베딩 오류: {str(embed_err)}")
                    # 임베딩 실패해도 계속 진행
                
                chunk_count += 1
                
                # 10개 청크마다 커밋
                if chunk_count % 10 == 0:
                    await db.commit()
                    print(f"{chunk_count}개 청크 중간 커밋 완료")
        
        except Exception as chunks_err:
            print(f"청크 처리 중 오류: {str(chunks_err)}")
            import traceback
            print(traceback.format_exc())
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"청크 처리 실패: {str(chunks_err)}")
        
        # 최종 커밋
        try:
            print("DB 커밋 중...")
            await db.commit()
        except Exception as commit_err:
            print(f"DB 커밋 오류: {str(commit_err)}")
            import traceback
            print(traceback.format_exc())
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"DB 커밋 실패: {str(commit_err)}")
        
        # FAISS 인덱스 저장
        try:
            print("FAISS 인덱스 저장 중...")
            embedding_service.save_index()
            print("업로드 및 임베딩 완료")
        except Exception as faiss_err:
            print(f"FAISS 인덱스 저장 오류: {str(faiss_err)}")
            # FAISS 저장 실패해도 계속 진행
        
        return {
            "message": "문서가 성공적으로 업로드되었습니다.",
            "document_id": document.id,
            "chunks_count": len(chunks)
        }
        
    except HTTPException:
        # 이미 처리된 예외는 그대로 전달
        raise
    except Exception as e:
        print(f"업로드 실패 상세 오류: {str(e)}")
        import traceback
        print(traceback.format_exc())
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"업로드 실패: {str(e)}")

@app.post("/search")
async def search_documents(
    query: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """문서 검색"""
    try:
        # 유사한 청크 검색
        similar_chunks = await embedding_service.search_similar(query, k=5)
        
        if not similar_chunks:
            return {"message": "관련 문서를 찾을 수 없습니다.", "results": []}
        
        return {
            "message": f"{len(similar_chunks)}개의 관련 문서를 찾았습니다.",
            "results": similar_chunks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")

@app.post("/chat")
async def chat_with_documents(
    query: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """문서 기반 채팅 (스트리밍)"""
    try:
        # CloudType 환경 감지
        IS_CLOUDTYPE = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
        
        if IS_CLOUDTYPE:
            print(f"CloudType 환경에서 채팅 요청: {query}")
        
        # 관련 문서 검색
        context_chunks = await embedding_service.search_similar(query, k=3)
        
        if not context_chunks:
            async def no_context_stream():
                if IS_CLOUDTYPE:
                    # CloudType 환경에서는 기본 응답 제공
                    yield "data: " + json.dumps({
                        "content": f"CloudType 환경에서 '{query}'에 대한 응답입니다. 현재 문서 검색 기능이 제한되어 있어 기본 응답을 제공합니다. 일반적인 질문이시라면 OpenAI GPT를 통해 답변드릴 수 있습니다.",
                        "done": True
                    }) + "\n\n"
                else:
                    yield "data: " + json.dumps({
                        "content": "죄송합니다. 업로드된 문서에서 관련 정보를 찾을 수 없습니다.",
                        "done": True
                    }) + "\n\n"
            
            return StreamingResponse(
                no_context_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache"}
            )
        
        # GPT 스트리밍 응답 생성
        stream = await chat_service.generate_response_stream(query, context_chunks)
        
        if not stream:
            async def error_stream():
                yield "data: " + json.dumps({
                    "content": "응답 생성 중 오류가 발생했습니다.",
                    "done": True
                }) + "\n\n"
            
            return StreamingResponse(
                error_stream(),
                media_type="text/plain",
                headers={"Cache-Control": "no-cache"}
            )
        
        async def generate_stream():
            try:
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield "data: " + json.dumps({
                            "content": content,
                            "done": False
                        }) + "\n\n"
                
                # 스트림 종료 신호
                yield "data: " + json.dumps({
                    "content": "",
                    "done": True
                }) + "\n\n"
                
            except Exception as e:
                print(f"스트리밍 중 오류: {e}")
                yield "data: " + json.dumps({
                    "content": f"스트리밍 중 오류: {str(e)}",
                    "done": True
                }) + "\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )
        
    except Exception as e:
        print(f"채팅 API 오류: {e}")
        import traceback
        print(traceback.format_exc())
        
        async def error_stream():
            yield "data: " + json.dumps({
                "content": f"채팅 실패: {str(e)}",
                "done": True
            }) + "\n\n"
        
        return StreamingResponse(
            error_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )
        
        return StreamingResponse(
            error_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )

@app.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """업로드된 문서 목록"""
    try:
        print("문서 목록 조회 시작...")
        print(f"DB 세션 타입: {type(db)}")
        print(f"CloudType 환경: {os.environ.get('CLOUDTYPE_DEPLOYMENT', '0')}")
        print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        
        # 모든 환경에서 데이터베이스 조회 시도
        try:
            # 쿼리 생성 및 실행
            stmt = select(Document).order_by(Document.created_at.desc())
            print(f"쿼리 생성: {stmt}")
            
            result = await db.execute(stmt)
            print("쿼리 실행 완료")
            documents = list(result.scalars().all())
            print(f"조회된 문서 수: {len(documents)}")
            
            return {
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "created_at": doc.created_at.isoformat()
                    }
                    for doc in documents
                ]
            }
            
        except Exception as db_err:
            print(f"데이터베이스 조회 실패: {str(db_err)}")
            import traceback
            print(traceback.format_exc())
            # 데이터베이스 실패 시에도 빈 목록 반환
            return {"documents": [], "error": f"데이터베이스 조회 실패: {str(db_err)}"}
            
    except Exception as e:
        print(f"문서 목록 조회 실패: {str(e)}")
        import traceback
        print(traceback.format_exc())
        # 모든 환경에서 오류 발생 시 빈 목록 반환
        return {"documents": [], "error": f"예외 발생: {str(e)}"}

if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except ImportError:
        print("uvicorn이 설치되지 않았습니다. pip install uvicorn으로 설치해주세요.")
