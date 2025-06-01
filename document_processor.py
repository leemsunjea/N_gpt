import os
import PyPDF2
import docx
import re
import unicodedata
from io import BytesIO

class DocumentProcessor:
    @staticmethod
    def clean_text(text):
        """텍스트에서 문제가 될 수 있는 문자들을 정제"""
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
    def extract_text_from_pdf(file_content):
        """PDF에서 텍스트 추출"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            # 텍스트 정제
            text = DocumentProcessor.clean_text(text)
            return text
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
            # 텍스트 정제
            text = DocumentProcessor.clean_text(text)
            return text
        except Exception as e:
            print(f"DOCX 텍스트 추출 실패: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_txt(file_content):
        """TXT에서 텍스트 추출"""
        try:
            text = file_content.decode('utf-8')
            # 텍스트 정제
            text = DocumentProcessor.clean_text(text)
            return text
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
