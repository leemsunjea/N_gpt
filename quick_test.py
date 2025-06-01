#!/usr/bin/env python3
import sys
import os

# 환경 설정
os.environ['CLOUDTYPE_DEPLOYMENT'] = '1'

try:
    from text_cleaner import TextCleaner
    print("✅ TextCleaner 모듈 로드 성공")
    
    # 간단한 텍스트 정제 테스트
    test_text = "테스트\x00텍스트"
    cleaned = TextCleaner.clean_for_postgresql(test_text)
    
    if '\x00' in cleaned:
        print("❌ NULL 바이트 제거 실패")
        sys.exit(1)
    else:
        print("✅ NULL 바이트 제거 성공")
    
    print("✅ 텍스트 정제 기능 정상 동작")
    
except ImportError as e:
    print(f"❌ 모듈 로드 실패: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    sys.exit(1)

print("🎉 기본 검증 완료!")
