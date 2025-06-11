import os
import PyPDF2 # PdfReadError 문제로 일단 주석 처리
import docx
import re
import unicodedata
from io import BytesIO
from PyPDF2 import PdfReader, PdfReadError # PdfReadError 문제로 일단 주석 처리

class DocumentProcessor:
    @staticmethod
    def clean_text(text):
        """텍스트에서 문제가 될 수 있는 문자들을 정제"""
        if not text:
            return ""
        
        text = str(text) # 입력이 문자열이 아닐 경우를 대비

        # 1. null 바이트 제거
        text = text.replace('\x00', '')
        
        # 2. 대체 문자 제거
        text = text.replace('\ufffd', '')
        
        # 3. 기타 제어 문자 제거 (탭, 개행, 캐리지 리턴은 유지)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        # 4. Unicode 정규화 (NFD -> NFC)
        try:
            text = unicodedata.normalize('NFC', text)
        except Exception as e:
            print(f"Unicode 정규화 중 오류 발생: {e}. 원본 텍스트 사용.")
            # 정규화 실패 시 오류 로깅 후 원본 텍스트 반환 또는 특정 처리
            pass # 일단 원본 텍스트로 계속 진행

        # 5. 비인쇄 가능한 Unicode 문자 제거 (더 엄격하게)
        cleaned_text = []
        for char in text:
            cat = unicodedata.category(char)
            # 일반적인 제어 문자(Cc), 형식 문자(Cf), 서러게이트(Cs), 개인용(Co), 할당되지 않음(Cn)
            if cat.startswith('C') and char not in '\t\n\r':
                continue
            cleaned_text.append(char)
        text = "".join(cleaned_text)
        
        # 6. 연속된 공백 정리 (줄바꿈 포함)
        text = re.sub(r'\s+', ' ', text) # 모든 공백 문자를 단일 공백으로
        text = text.strip() # 앞뒤 공백 제거
        
        return text
    
    @staticmethod
    def extract_text_from_pdf(file_content):
        """PDF에서 텍스트 추출"""
        try:
            # PyPDF2 관련 코드는 PdfReadError 문제 해결 후 활성화
            pdf_reader = PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text: 
                    text += DocumentProcessor.clean_text(page_text) + "\\n" # 각 페이지 텍스트 정제
            return text.strip() # 최종 텍스트의 앞뒤 공백 제거
        except PdfReadError as pre: 
            print(f"PDF 읽기 오류 (PyPDF2): {pre}")
            return "" # 오류 발생 시 빈 문자열 반환
        except Exception as e:
            print(f"PDF 텍스트 추출 중 일반 오류 발생: {e}")
            return "" # 오류 발생 시 빈 문자열 반환
        # print("PyPDF2 라이브러리 문제로 PDF 처리가 비활성화되었습니다.") # 이 줄은 제거하거나 주석 처리
        # return "" # 임시로 빈 문자열 반환 -> 이 줄은 제거

    @staticmethod
    def extract_text_from_docx(file_content):
        """DOCX에서 텍스트 추출"""
        try:
            doc = docx.Document(BytesIO(file_content))
            text_parts = []
            for paragraph in doc.paragraphs:
                text_parts.append(paragraph.text)
            full_text = "\n".join(text_parts)
            return DocumentProcessor.clean_text(full_text)
        except Exception as e:
            print(f"DOCX 텍스트 추출 실패: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_txt(file_content):
        """TXT에서 텍스트 추출"""
        try:
            # 다양한 인코딩 시도 (가장 일반적인 것부터)
            encodings_to_try = ['utf-8', 'euc-kr', 'cp949', 'latin-1']
            decoded_text = None
            for encoding in encodings_to_try:
                try:
                    decoded_text = file_content.decode(encoding)
                    break # 성공하면 루프 종료
                except UnicodeDecodeError:
                    continue # 다음 인코딩 시도
            
            if decoded_text is None:
                # 모든 인코딩 시도 실패 시, errors='ignore'로 강제 디코딩
                decoded_text = file_content.decode('utf-8', errors='ignore')
                print(f"TXT 파일 디코딩 실패. 일부 문자가 손실될 수 있습니다.")

            return DocumentProcessor.clean_text(decoded_text)
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
