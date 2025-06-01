/**
 * 메인 JavaScript 파일
 * 프로젝트의 클라이언트 측 기능을 구현합니다
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('문서가 로드되었습니다.');
    
    // UI 요소
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const messagesContainer = document.getElementById('messages');
    const uploadForm = document.getElementById('upload-form');
    
    // 채팅 폼 제출 이벤트 처리
    if (chatForm) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const query = chatInput.value.trim();
            if (!query) return;

            // 참고 문서 출처 콘솔에 출력
            try {
                const searchRes = await fetch('/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({ query })
                });
                const searchData = await searchRes.json();
                console.log('참고 문서 출처:', searchData.results);
            } catch (err) {
                console.error('출처 조회 실패:', err);
            }

            // 사용자 메시지 표시
            appendMessage('user', query);
            chatInput.value = '';

            // 봇 메시지 컨테이너 생성
            const botMessageElement = document.createElement('div');
            botMessageElement.className = 'message bot-message';
            messagesContainer.appendChild(botMessageElement);

            try {
                // 스트리밍 응답 처리
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({ query })
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let botResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    const lines = text.split('\n\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.substring(6));
                                if (!data.done) {
                                    botResponse += data.content;
                                    // Markdown 렌더링
                                    botMessageElement.innerHTML = `<div class="markdown-content">${marked.parse(botResponse)}</div>`;
                                }
                            } catch (e) {
                                console.error('JSON 파싱 에러:', e);
                            }
                        }
                    }
                }
                // 스크롤 아래로
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            } catch (error) {
                console.error('오류:', error);
                appendMessage('bot', '❌ 오류가 발생했습니다: ' + error.message);
            } finally {
                sendButton.disabled = false;
            }
        });
    }
    
    // 파일 업로드 폼 제출 이벤트 처리
    if (uploadForm) {
        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(uploadForm);
            const submitButton = uploadForm.querySelector('button[type="submit"]');
            const statusElement = document.getElementById('upload-status');
            
            if (statusElement) {
                statusElement.textContent = '업로드 중...';
            }
            
            if (submitButton) {
                submitButton.disabled = true;
            }
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (statusElement) {
                    statusElement.textContent = result.message;
                }
                
                // 문서 목록 새로고침
                refreshDocumentsList();
                
            } catch (error) {
                console.error('업로드 오류:', error);
                if (statusElement) {
                    statusElement.textContent = '업로드 실패: ' + error.message;
                }
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        });
    }
    
    // 문서 목록 새로고침 함수
    async function refreshDocumentsList() {
        const documentsContainer = document.getElementById('documents-list');
        if (!documentsContainer) return;
        
        try {
            const response = await fetch('/documents');
            const data = await response.json();
            
            documentsContainer.innerHTML = '';
            
            if (data.documents && data.documents.length > 0) {
                data.documents.forEach(doc => {
                    const docElement = document.createElement('div');
                    docElement.className = 'document-item';
                    
                    const date = new Date(doc.created_at).toLocaleString();
                    docElement.innerHTML = `
                        <strong>${doc.filename}</strong>
                        <span class="document-date">${date}</span>
                    `;
                    
                    documentsContainer.appendChild(docElement);
                });
            } else {
                documentsContainer.innerHTML = '<p>업로드된 문서가 없습니다.</p>';
            }
            
        } catch (error) {
            console.error('문서 목록 조회 오류:', error);
            documentsContainer.innerHTML = '<p>문서 목록을 불러오는 데 실패했습니다.</p>';
        }
    }
    
    // 초기 문서 목록 로드
    refreshDocumentsList();
    
    // 메시지 추가 헬퍼 함수
    function appendMessage(type, content) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}-message`;
        messageElement.textContent = content;
        messagesContainer.appendChild(messageElement);
        
        // 스크롤을 가장 아래로 이동
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
});
