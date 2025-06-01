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
