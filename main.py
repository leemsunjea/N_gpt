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
    
    # favicon.ico 파일 확인 및 생성
    favicon_path = "static/favicon.ico"
    if not os.path.exists(favicon_path):
        print(f"{favicon_path} 파일이 없어 생성합니다.")
        with open(favicon_path, "wb") as f:
            f.write(b"")  # 빈 파일 생성
    
    # 템플릿 파일 확인
    template_path = "templates/index.html"
    if not os.path.exists(template_path):
        print(f"{template_path} 파일이 없어 기본 템플릿을 생성합니다.")
        with open(template_path, "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>N_GPT Document Search</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="icon" href="/static/favicon.ico">
</head>
<body>
    <div class="container">
        <h1>N_GPT 문서 검색</h1>
        <div class="upload-section">
            <h2>문서 업로드</h2>
            <form id="upload-form" enctype="multipart/form-data">
                <input type="file" id="file" name="file" accept=".pdf,.docx,.txt">
                <button type="submit">업로드</button>
            </form>
            <div id="upload-status"></div>
        </div>
        
        <div class="documents-section">
            <h2>업로드된 문서</h2>
            <ul id="documents-list"></ul>
        </div>
        
        <div class="search-section">
            <h2>검색</h2>
            <form id="search-form">
                <input type="text" id="query" name="query" placeholder="검색어를 입력하세요...">
                <button type="submit">검색</button>
            </form>
            <div id="search-results"></div>
        </div>
        
        <div class="chat-section">
            <h2>문서 기반 채팅</h2>
            <div id="chat-messages"></div>
            <form id="chat-form">
                <input type="text" id="chat-query" name="query" placeholder="질문을 입력하세요...">
                <button type="submit">전송</button>
            </form>
        </div>
    </div>
    
    <script src="/static/main.js"></script>
</body>
</html>""")
    
    # 정적 파일 확인
    css_path = "static/style.css"
    if not os.path.exists(css_path):
        print(f"{css_path} 파일이 없어 기본 스타일을 생성합니다.")
        with open(css_path, "w", encoding="utf-8") as f:
            f.write("""body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background-color: #f5f5f5;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    background-color: white;
    padding: 20px;
    border-radius: 5px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

h1 {
    text-align: center;
    color: #333;
}

h2 {
    color: #444;
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
}

.upload-section, .documents-section, .search-section, .chat-section {
    margin-bottom: 30px;
}

form {
    display: flex;
    margin-bottom: 15px;
}

input[type="text"], input[type="file"] {
    flex: 1;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

button {
    padding: 8px 15px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    margin-left: 10px;
}

button:hover {
    background-color: #45a049;
}

#upload-status, #search-results {
    margin-top: 15px;
    padding: 10px;
    border-radius: 4px;
}

#documents-list {
    list-style-type: none;
    padding: 0;
}

#documents-list li {
    padding: 8px;
    border-bottom: 1px solid #eee;
}

#chat-messages {
    height: 300px;
    overflow-y: auto;
    border: 1px solid #ddd;
    padding: 10px;
    margin-bottom: 15px;
    border-radius: 4px;
    background-color: #f9f9f9;
}

.user-message, .assistant-message {
    margin-bottom: 10px;
    padding: 8px;
    border-radius: 4px;
}

.user-message {
    background-color: #e1f5fe;
    text-align: right;
}

.assistant-message {
    background-color: #f0f0f0;
}""")
    
    js_path = "static/main.js"
    if not os.path.exists(js_path):
        print(f"{js_path} 파일이 없어 기본 스크립트를 생성합니다.")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("""document.addEventListener('DOMContentLoaded', function() {
    // 문서 목록 로드
    loadDocuments();
    
    // 폼 제출 이벤트 리스너
    document.getElementById('upload-form').addEventListener('submit', uploadDocument);
    document.getElementById('search-form').addEventListener('submit', searchDocuments);
    document.getElementById('chat-form').addEventListener('submit', startChat);
});

// 문서 업로드
async function uploadDocument(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('file');
    const statusDiv = document.getElementById('upload-status');
    
    if (!fileInput.files.length) {
        statusDiv.textContent = '파일을 선택해주세요.';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    statusDiv.textContent = '업로드 중...';
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            statusDiv.textContent = result.message;
            loadDocuments();  // 목록 새로고침
        } else {
            statusDiv.textContent = `오류: ${result.detail}`;
        }
    } catch (error) {
        statusDiv.textContent = `업로드 중 오류 발생: ${error.message}`;
    }
}

// 문서 목록 로드
async function loadDocuments() {
    const listElement = document.getElementById('documents-list');
    listElement.innerHTML = '로딩 중...';
    
    try {
        const response = await fetch('/documents');
        const result = await response.json();
        
        if (response.ok) {
            if (result.documents && result.documents.length > 0) {
                listElement.innerHTML = '';
                result.documents.forEach(doc => {
                    const li = document.createElement('li');
                    const date = new Date(doc.created_at).toLocaleString();
                    li.textContent = `${doc.filename} (업로드: ${date})`;
                    listElement.appendChild(li);
                });
            } else {
                listElement.innerHTML = '업로드된 문서가 없습니다.';
            }
        } else {
            listElement.innerHTML = `오류: ${result.detail || '문서 목록을 가져올 수 없습니다.'}`;
        }
    } catch (error) {
        listElement.innerHTML = `문서 목록을 가져오는 중 오류 발생: ${error.message}`;
    }
}

// 문서 검색
async function searchDocuments(event) {
    event.preventDefault();
    
    const queryInput = document.getElementById('query');
    const resultsDiv = document.getElementById('search-results');
    
    if (!queryInput.value.trim()) {
        resultsDiv.innerHTML = '검색어를 입력해주세요.';
        return;
    }
    
    resultsDiv.innerHTML = '검색 중...';
    
    const formData = new FormData();
    formData.append('query', queryInput.value);
    
    try {
        const response = await fetch('/search', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            if (result.results && result.results.length > 0) {
                resultsDiv.innerHTML = `<p>${result.message}</p>`;
                
                const ol = document.createElement('ol');
                result.results.forEach(item => {
                    const li = document.createElement('li');
                    li.innerHTML = `<div>${item.text}</div><small>관련도: ${Math.round(item.score * 100)}%</small>`;
                    ol.appendChild(li);
                });
                
                resultsDiv.appendChild(ol);
            } else {
                resultsDiv.innerHTML = '관련 문서를 찾을 수 없습니다.';
            }
        } else {
            resultsDiv.innerHTML = `오류: ${result.detail}`;
        }
    } catch (error) {
        resultsDiv.innerHTML = `검색 중 오류 발생: ${error.message}`;
    }
}

// 문서 기반 채팅
async function startChat(event) {
    event.preventDefault();
    
    const queryInput = document.getElementById('chat-query');
    const chatDiv = document.getElementById('chat-messages');
    
    if (!queryInput.value.trim()) {
        return;
    }
    
    // 사용자 메시지 추가
    const userDiv = document.createElement('div');
    userDiv.className = 'user-message';
    userDiv.textContent = queryInput.value;
    chatDiv.appendChild(userDiv);
    
    // 스크롤 아래로
    chatDiv.scrollTop = chatDiv.scrollHeight;
    
    const formData = new FormData();
    formData.append('query', queryInput.value);
    
    // 입력 필드 초기화
    const question = queryInput.value;
    queryInput.value = '';
    
    // 응답 메시지 컨테이너 추가
    const responseDiv = document.createElement('div');
    responseDiv.className = 'assistant-message';
    responseDiv.textContent = '생각 중...';
    chatDiv.appendChild(responseDiv);
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        responseDiv.textContent = '';
        
        while (true) {
            const { value, done } = await reader.read();
            
            if (done) {
                break;
            }
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.content) {
                        responseDiv.innerHTML += data.content;
                    }
                    
                    // 스크롤 아래로
                    chatDiv.scrollTop = chatDiv.scrollHeight;
                }
            }
        }
    } catch (error) {
        responseDiv.textContent = `오류가 발생했습니다: ${error.message}`;
    }
    
    // 스크롤 아래로
    chatDiv.scrollTop = chatDiv.scrollHeight;
}
""")
    
    # CloudType 환경에서는 외부 데이터베이스를 사용하므로 테이블 생성을 시도하지 않음
    if os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1':
        print("CloudType 환경 감지: 외부 PostgreSQL 데이터베이스 사용 - 테이블 생성 건너뜀")
        return
        
    try:
        await create_tables()
        print("데이터베이스 테이블 생성 완료")
    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
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
            document = Document(
                filename=file.filename,
                content=text_content
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
            chunks = DocumentProcessor.chunk_text(text_content)
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
                
                # 데이터베이스에 청크 저장
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_text=chunk_text,
                    chunk_index=i
                )
                db.add(chunk)
                await db.flush()
                
                # FAISS 인덱스에 추가
                print(f"청크 {i+1} 임베딩 생성 중...")
                try:
                    embedding = embedding_service.add_to_index(chunk.id, chunk_text)
                    
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
        print("문서 목록 조회 시작...")
        print(f"DB 세션 타입: {type(db)}")
        print(f"CloudType 환경: {os.environ.get('CLOUDTYPE_DEPLOYMENT', '0')}")
        print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        
        # 데이터베이스 연결 테스트
        try:
            await db.connection()
            print("데이터베이스 연결 성공")
        except Exception as conn_err:
            print(f"데이터베이스 연결 테스트 실패: {str(conn_err)}")
            import traceback
            print(traceback.format_exc())
        
        # 쿼리 생성 및 실행
        stmt = select(Document).order_by(Document.created_at.desc())
        print(f"쿼리 생성: {stmt}")
        
        try:
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
        except Exception as query_err:
            print(f"쿼리 실행 실패: {str(query_err)}")
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"쿼리 실행 실패: {str(query_err)}")
            
    except Exception as e:
        print(f"문서 목록 조회 실패 상세 오류: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        # CloudType 환경에서는 빈 목록 반환 (임시 조치)
        if os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1':
            print("CloudType 환경에서 오류 발생, 빈 목록 반환")
            return {"documents": []}
            
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
