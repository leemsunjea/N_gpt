import os
import openai
from dotenv import load_dotenv

load_dotenv()

class ChatService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        # CloudType 환경 감지
        self.is_cloudtype = os.environ.get('CLOUDTYPE_DEPLOYMENT', '0') == '1'
    
    async def generate_response_stream(self, query, context_chunks):
        """컨텍스트를 기반으로 스트리밍 응답 생성"""
        try:
            # OpenAI API 키 확인
            if not os.getenv("OPENAI_API_KEY"):
                print("OpenAI API 키가 설정되지 않음")
                return None
            
            # 컨텍스트 구성
            context = "\n\n".join([
                f"문서 {i+1}:\n{chunk['text']}"
                for i, chunk in enumerate(context_chunks)
            ])
            
            # CloudType 환경에서는 간단한 프롬프트 사용
            if self.is_cloudtype:
                system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 주어진 정보를 바탕으로 간결하고 정확한 답변을 제공하세요."""
                user_prompt = f"""다음 정보를 참고하여 질문에 답변해주세요:

{context}

질문: {query}"""
            else:
                # 로컬 환경에서는 상세한 프롬프트 사용
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
            import traceback
            print(traceback.format_exc())
            
            # API 할당량 초과 또는 기타 오류 시 대체 응답 생성
            return self._generate_fallback_response(query, context_chunks, str(e))
    
    def _generate_fallback_response(self, query, context_chunks, error_msg):
        """API 오류 시 대체 응답 생성"""
        async def fallback_stream():
            # 할당량 초과 확인
            if "quota" in error_msg.lower() or "429" in error_msg:
                fallback_content = f"""## 📚 문서 기반 응답

**질문**: {query}

**참고 문서**:
"""
                
                # 컨텍스트가 있으면 관련 내용 표시
                if context_chunks:
                    for i, chunk in enumerate(context_chunks):
                        text = chunk.get('text', '')[:200] + "..." if len(chunk.get('text', '')) > 200 else chunk.get('text', '')
                        fallback_content += f"\n**문서 {i+1}**:\n{text}\n"
                    
                    fallback_content += f"""
**답변**: 죄송합니다. 현재 AI 서비스 할당량이 초과되어 자동 응답을 생성할 수 없습니다. 
하지만 위의 관련 문서 내용을 참고하시면 '{query}'에 대한 정보를 찾으실 수 있습니다.

문서를 직접 확인해보시기 바랍니다. 🔍
"""
                else:
                    fallback_content = f"""## ❌ 검색 결과 없음

**질문**: {query}

죄송합니다. 업로드된 문서에서 관련 정보를 찾을 수 없습니다.
다른 키워드로 다시 검색해보시거나 관련 문서를 업로드해주세요.
"""
            else:
                fallback_content = f"""## ⚠️ 일시적 오류

**질문**: {query}

죄송합니다. 일시적인 시스템 오류가 발생했습니다.
잠시 후 다시 시도해주세요.

**오류 내용**: {error_msg}
"""
            
            # 청크 단위로 스트리밍 시뮬레이션
            chunks = fallback_content.split('\n')
            for chunk in chunks:
                if chunk.strip():
                    yield type('MockChunk', (), {
                        'choices': [type('Choice', (), {
                            'delta': type('Delta', (), {
                                'content': chunk + '\n'
                            })()
                        })()]
                    })()
                    # 약간의 지연으로 스트리밍 효과
                    import asyncio
                    await asyncio.sleep(0.05)
        
        return fallback_stream()

# 전역 채팅 서비스 인스턴스
chat_service = ChatService()
