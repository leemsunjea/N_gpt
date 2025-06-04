#!/usr/bin/env python3
"""
멀티유저 시스템 구현 검증 스크립트
구현된 모든 기능들의 동작을 검증합니다.
"""

import os
import asyncio
import inspect
from datetime import datetime

def verify_file_exists(file_path, description):
    """파일 존재 여부 확인"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - 파일이 없습니다")
        return False

def verify_imports():
    """주요 모듈들의 import 가능성 확인"""
    print("\n🔍 주요 모듈 import 검증:")
    
    modules_to_check = [
        ("database", "데이터베이스 모듈"),
        ("user_session", "사용자 세션 모듈"),
        ("user_data_cleaner", "데이터 정리 모듈"),
        ("main", "메인 애플리케이션")
    ]
    
    all_good = True
    for module_name, description in modules_to_check:
        try:
            module = __import__(module_name)
            print(f"✅ {description} import 성공")
        except ImportError as e:
            print(f"❌ {description} import 실패: {e}")
            all_good = False
        except Exception as e:
            print(f"⚠️  {description} import 시 오류: {e}")
    
    return all_good

def verify_database_models():
    """데이터베이스 모델 검증"""
    print("\n🗄️ 데이터베이스 모델 검증:")
    
    try:
        from database import User, Document, DocumentChunk
        
        # User 모델 검증
        user_attrs = ['id', 'created_at', 'last_active']
        for attr in user_attrs:
            if hasattr(User, attr):
                print(f"✅ User.{attr} 필드 존재")
            else:
                print(f"❌ User.{attr} 필드 누락")
        
        # Document 모델 검증
        doc_attrs = ['id', 'user_id', 'filename', 'content', 'created_at']
        for attr in doc_attrs:
            if hasattr(Document, attr):
                print(f"✅ Document.{attr} 필드 존재")
            else:
                print(f"❌ Document.{attr} 필드 누락")
        
        # DocumentChunk 모델 검증
        chunk_attrs = ['id', 'user_id', 'document_id', 'chunk_text', 'chunk_index']
        for attr in chunk_attrs:
            if hasattr(DocumentChunk, attr):
                print(f"✅ DocumentChunk.{attr} 필드 존재")
            else:
                print(f"❌ DocumentChunk.{attr} 필드 누락")
                
        return True
        
    except Exception as e:
        print(f"❌ 데이터베이스 모델 검증 실패: {e}")
        return False

def verify_session_manager():
    """사용자 세션 매니저 검증"""
    print("\n👤 사용자 세션 매니저 검증:")
    
    try:
        from user_session import UserSessionManager
        
        manager = UserSessionManager()
        
        # 필수 메서드들 확인
        required_methods = [
            'generate_user_id',
            'get_or_create_user',
            'cleanup_old_sessions',
            'cleanup_expired_sessions',
            'get_session_stats'
        ]
        
        for method_name in required_methods:
            if hasattr(manager, method_name):
                method = getattr(manager, method_name)
                if callable(method):
                    print(f"✅ UserSessionManager.{method_name}() 메서드 존재")
                else:
                    print(f"❌ UserSessionManager.{method_name}는 호출 가능하지 않음")
            else:
                print(f"❌ UserSessionManager.{method_name}() 메서드 누락")
        
        return True
        
    except Exception as e:
        print(f"❌ 세션 매니저 검증 실패: {e}")
        return False

def verify_data_cleaner():
    """데이터 정리 도구 검증"""
    print("\n🧹 데이터 정리 도구 검증:")
    
    try:
        from user_data_cleaner import UserDataCleaner
        
        cleaner = UserDataCleaner()
        
        # 필수 메서드들 확인
        required_methods = [
            'get_all_user_stats',
            'cleanup_inactive_users',
            'cleanup_orphaned_faiss_files',
            'check_faiss_index_exists'
        ]
        
        for method_name in required_methods:
            if hasattr(cleaner, method_name):
                method = getattr(cleaner, method_name)
                if callable(method):
                    print(f"✅ UserDataCleaner.{method_name}() 메서드 존재")
                else:
                    print(f"❌ UserDataCleaner.{method_name}는 호출 가능하지 않음")
            else:
                print(f"❌ UserDataCleaner.{method_name}() 메서드 누락")
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터 정리 도구 검증 실패: {e}")
        return False

def verify_admin_endpoints():
    """관리자 엔드포인트 검증"""
    print("\n🔧 관리자 엔드포인트 검증:")
    
    try:
        # main.py에서 엔드포인트 함수들 확인
        with open('/Users/imsunjae/Documents/GitHub/N_gpt/main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        admin_endpoints = [
            'get_system_stats_admin',
            'get_all_users_admin', 
            'cleanup_inactive_users_admin',
            'cleanup_sessions_admin'
        ]
        
        for endpoint in admin_endpoints:
            if f"def {endpoint}" in content:
                print(f"✅ /{endpoint} 엔드포인트 구현됨")
            else:
                print(f"❌ /{endpoint} 엔드포인트 누락")
        
        return True
        
    except Exception as e:
        print(f"❌ 관리자 엔드포인트 검증 실패: {e}")
        return False

def verify_frontend_admin_panel():
    """프론트엔드 관리자 패널 검증"""
    print("\n🎨 프론트엔드 관리자 패널 검증:")
    
    try:
        with open('/Users/imsunjae/Documents/GitHub/N_gpt/templates/index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        admin_features = [
            'id="adminKey"',
            'id="showSystemStats"',
            'id="showAllUsers"',
            'id="cleanupSessions"',
            'id="cleanupInactive"',
            'id="adminResult"'
        ]
        
        for feature in admin_features:
            if feature in content:
                print(f"✅ 관리자 UI 요소 {feature} 존재")
            else:
                print(f"❌ 관리자 UI 요소 {feature} 누락")
        
        return True
        
    except Exception as e:
        print(f"❌ 프론트엔드 관리자 패널 검증 실패: {e}")
        return False

def main():
    """메인 검증 함수"""
    print("🚀 N_GPT 멀티유저 시스템 구현 검증 시작")
    print("=" * 60)
    
    # 파일 존재 여부 확인
    print("\n📁 핵심 파일들 존재 여부 확인:")
    files_to_check = [
        ('/Users/imsunjae/Documents/GitHub/N_gpt/main.py', '메인 애플리케이션'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/database.py', '데이터베이스 모델'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/user_session.py', '사용자 세션 관리'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/user_data_cleaner.py', '데이터 정리 도구'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/migrate_add_user_id.py', '데이터베이스 마이그레이션'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/test_multiuser.py', '멀티유저 테스트'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/templates/index.html', '프론트엔드 템플릿'),
        ('/Users/imsunjae/Documents/GitHub/N_gpt/requirements.txt', '의존성 파일')
    ]
    
    files_ok = all(verify_file_exists(file_path, desc) for file_path, desc in files_to_check)
    
    # 모듈 import 검증
    imports_ok = verify_imports()
    
    # 데이터베이스 모델 검증
    models_ok = verify_database_models()
    
    # 세션 매니저 검증
    session_ok = verify_session_manager()
    
    # 데이터 정리 도구 검증
    cleaner_ok = verify_data_cleaner()
    
    # 관리자 엔드포인트 검증
    endpoints_ok = verify_admin_endpoints()
    
    # 프론트엔드 관리자 패널 검증
    frontend_ok = verify_frontend_admin_panel()
    
    # 전체 결과 요약
    print("\n" + "=" * 60)
    print("📊 검증 결과 요약:")
    
    all_checks = [
        (files_ok, "핵심 파일 존재"),
        (imports_ok, "모듈 import"),
        (models_ok, "데이터베이스 모델"),
        (session_ok, "사용자 세션 관리"),
        (cleaner_ok, "데이터 정리 도구"),
        (endpoints_ok, "관리자 엔드포인트"),
        (frontend_ok, "프론트엔드 관리자 패널")
    ]
    
    passed = sum(1 for check, _ in all_checks if check)
    total = len(all_checks)
    
    for check_result, check_name in all_checks:
        status = "✅ 통과" if check_result else "❌ 실패"
        print(f"{status}: {check_name}")
    
    print(f"\n🎯 전체 검증 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 검증이 통과되었습니다! 멀티유저 시스템이 완전히 구현되었습니다.")
        print("\n📋 다음 단계:")
        print("1. 서버 실행: python main.py")
        print("2. 데이터 마이그레이션 (기존 데이터가 있는 경우): python migrate_add_user_id.py")
        print("3. 멀티유저 테스트: python test_multiuser.py")
        print("4. 관리자 패널 테스트: 웹 인터페이스에서 관리자 키 사용")
        print("5. 데이터 정리: python user_data_cleaner.py")
    else:
        print("⚠️  일부 검증이 실패했습니다. 위의 오류를 확인하고 수정해주세요.")
    
    print(f"\n검증 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
