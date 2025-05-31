import os
import PyPDF2
import docx
from io import BytesIO

class DocumentProcessor:
    @staticmethod
    def extract_text_from_pdf(file_content):
        """PDF에서 텍스트 추출"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"PDF 텍스트 추출 실패: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_docx(file_content):
        """DOCX에서 텍스트 추출"""
        try:
            doc = docx.Document(BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"DOCX 텍스트 추출 실패: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_txt(file_content):
        """TXT에서 텍스트 추출"""
        try:
            return file_content.decode('utf-8')
        except Exception as e:
            print(f"TXT 텍스트 추출 실패: {e}")
            return ""
    
    @staticmethod
    def extract_text(filename, file_content):
        """파일 확장자에 따라 텍스트 추출"""
        file_extension = filename.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            return DocumentProcessor.extract_text_from_pdf(file_content)
        elif file_extension == 'docx':
            return DocumentProcessor.extract_text_from_docx(file_content)
        elif file_extension == 'txt':
            return DocumentProcessor.extract_text_from_txt(file_content)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_extension}")
    
    @staticmethod
    def chunk_text(text, chunk_size=500, overlap=50):
        """텍스트를 청크로 분할"""
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 문장 경계에서 자르기 위해 조정
            if end < len(text):
                # 마지막 마침표, 느낌표, 물음표 찾기
                for punct in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
                    last_punct = text.rfind(punct, start, end)
                    if last_punct > start:
                        end = last_punct + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            
            # 무한 루프 방지
            if start >= len(text):
                break
        
        return chunks
