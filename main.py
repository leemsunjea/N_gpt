from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import os
import uvicorn

from database import get_db, create_tables, Document, DocumentChunk
from document_processor import DocumentProcessor
# 경량 임베딩 서비스 사용
from lightweight_embedding import embedding_service
from chat_service import chat_service

app = FastAPI(title="N_GPT Document Search", version="1.0.0")

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 초기화"""
    import os
    
    # 필요한 디렉토리 생성
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    try:
        await create_tables()
        print("데이터베이스 테이블 생성 완료")
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        print("SQLite로 대체 시도...")
        
        # 환경 변수 강제 설정으로 SQLite 사용 확인
        os.environ['CLOUDTYPE_DEPLOYMENT'] = '1'
        
        # 데이터베이스 재초기화 시도
        from database import create_tables
        await create_tables()
        print("SQLite 데이터베이스 테이블 생성 완료")

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
        # 파일 내용 읽기
        file_content = await file.read()
        
        # 텍스트 추출
        text_content = DocumentProcessor.extract_text(file.filename, file_content)
        
        if not text_content:
            raise HTTPException(status_code=400, detail="텍스트를 추출할 수 없습니다.")
        
        # 문서 저장
        document = Document(
            filename=file.filename,
            content=text_content
        )
        db.add(document)
        await db.flush()  # ID 생성을 위해
        
        # 텍스트 청킹
        chunks = DocumentProcessor.chunk_text(text_content)
        
        # 각 청크를 임베딩하고 저장
        for i, chunk_text in enumerate(chunks):
            # 데이터베이스에 청크 저장
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_text=chunk_text,
                chunk_index=i
            )
            db.add(chunk)
            await db.flush()
            
            # FAISS 인덱스에 추가
            embedding = embedding_service.add_to_index(chunk.id, chunk_text)
            
            # 임베딩을 데이터베이스에 저장
            if embedding:
                chunk.embedding = json.dumps(embedding)
        
        await db.commit()
        
        # FAISS 인덱스 저장
        embedding_service.save_index()
        
        return {
            "message": "문서가 성공적으로 업로드되었습니다.",
            "document_id": document.id,
            "chunks_count": len(chunks)
        }
        
    except Exception as e:
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
        # 관련 문서 검색
        context_chunks = await embedding_service.search_similar(query, k=3)
        
        if not context_chunks:
            async def no_context_stream():
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
                async for chunk in stream:
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

@app.get("/documents")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """업로드된 문서 목록"""
    try:
        stmt = select(Document).order_by(Document.created_at.desc())
        result = await db.execute(stmt)
        documents = result.scalars().all()
        
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
