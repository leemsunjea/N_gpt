import os
import openai
from dotenv import load_dotenv

load_dotenv()

class ChatService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
    
    async def generate_response_stream(self, query, context_chunks):
        """컨텍스트를 기반으로 스트리밍 응답 생성"""
        try:
            # 컨텍스트 구성
            context = "\n\n".join([
                f"문서 {i+1}:\n{chunk['text']}"
                for i, chunk in enumerate(context_chunks)
            ])
            
            # 프롬프트 구성
            system_prompt = """당신은 업로드된 문서를 바탕으로 질문에 답변하는 AI 어시스턴트입니다.
            
규칙:
1. 제공된 문서 컨텍스트를 바탕으로만 답변하세요.
2. 문서에 없는 내용은 추측하지 마세요.
3. 답변은 항상 마크다운 형식으로 작성하세요.
4. 문서에서 찾을 수 없는 정보라면 그렇게 명시하세요.
5. 가능하면 문서의 어느 부분에서 정보를 찾았는지 언급하세요."""

            user_prompt = f"""다음 문서들을 참고하여 질문에 답변해주세요:

{context}

질문: {query}

답변을 마크다운 형식으로 작성해주세요."""

            # 스트리밍 응답 생성
            stream = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=1000
            )
            
            return stream
            
        except Exception as e:
            print(f"GPT 응답 생성 실패: {e}")
            return None

# 전역 채팅 서비스 인스턴스
chat_service = ChatService()
