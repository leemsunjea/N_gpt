# N_GPT - Document Search & Chat

문서를 업로드하고 AI와 대화할 수 있는 RAG(Retrieval-Augmented Generation) 시스템입니다.

## ✨ 주요 기능

- 📄 **문서 업로드**: PDF, DOCX, TXT 파일 지원
- 🔍 **임베딩 검색**: FAISS를 이용한 벡터 검색
- 💬 **실시간 채팅**: GPT 스트리밍 응답
- 📊 **데이터베이스 연동**: PostgreSQL을 통한 데이터 영속성
- 🎨 **모던 UI**: Tailwind CSS를 활용한 반응형 웹 인터페이스

## 🛠 기술 스택

- **Backend**: FastAPI, SQLAlchemy, AsyncPG
- **AI/ML**: OpenAI GPT-3.5, Sentence Transformers, FAISS
- **Database**: PostgreSQL
- **Frontend**: HTML, JavaScript, Tailwind CSS
- **Deployment**: Docker

## 📋 요구사항

- Python 3.11+
- PostgreSQL 데이터베이스
- OpenAI API 키

## 🚀 설치 및 실행

### 로컬 실행

1. **저장소 클론**
   ```bash
   git clone <repository-url>
   cd N_gpt
   ```

2. **가상환경 생성 및 활성화**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

4. **환경변수 설정**
   `.env` 파일을 생성하고 다음 내용을 추가:
   ```
   DATABASE_URL=postgresql+asyncpg://username:password@host:port/database
   OPENAI_API_KEY=your_openai_api_key
   ```

5. **애플리케이션 실행**
   ```bash
   python main.py
   ```

### Docker 실행

1. **Docker 이미지 빌드**
   ```bash
   docker build -t n-gpt .
   ```

2. **컨테이너 실행**
   ```bash
   docker run -p 8000:8000 --env-file .env n-gpt
   ```

## 📖 사용법

1. **문서 업로드**
   - 웹 인터페이스에서 PDF, DOCX, TXT 파일 업로드
   - 시스템이 자동으로 텍스트 추출 및 임베딩 생성

2. **질문하기**
   - 채팅 창에 문서 관련 질문 입력
   - AI가 업로드된 문서를 기반으로 실시간 응답 제공

3. **검색 결과**
   - 모든 응답은 마크다운 형식으로 제공
   - 문서의 관련 부분을 참조하여 정확한 답변 생성

## 📁 프로젝트 구조

```
N_gpt/
├── main.py                 # FastAPI 메인 애플리케이션
├── database.py            # 데이터베이스 설정 및 모델
├── embedding_service.py   # 임베딩 및 FAISS 검색 서비스
├── document_processor.py  # 문서 처리 (텍스트 추출, 청킹)
├── chat_service.py        # OpenAI GPT 채팅 서비스
├── requirements.txt       # Python 의존성
├── Dockerfile            # Docker 설정
├── .env                  # 환경변수 (생성 필요)
└── templates/
    └── index.html        # 웹 인터페이스
```

## 🔧 API 엔드포인트

- `GET /` - 웹 인터페이스
- `POST /upload` - 문서 업로드
- `POST /search` - 문서 검색
- `POST /chat` - AI 채팅 (스트리밍)
- `GET /documents` - 업로드된 문서 목록

## 🌐 배포

### Cloudtype 배포

1. Dockerfile이 포함된 프로젝트를 Git 저장소에 푸시
2. Cloudtype에서 새 프로젝트 생성
3. 환경변수 설정:
   - `DATABASE_URL`
   - `OPENAI_API_KEY`
4. 자동 배포 완료

## 📝 라이선스

MIT License

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.