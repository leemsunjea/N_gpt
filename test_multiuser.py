#!/usr/bin/env python3
"""
N_GPT 멀티유저 시스템 테스트 스크립트
"""

import asyncio
import os
import requests
import json
from datetime import datetime

class NGPTTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.admin_key = os.environ.get("ADMIN_KEY", "admin123")
    
    def test_user_stats(self):
        """사용자 통계 API 테스트"""
        print("🧪 사용자 통계 API 테스트")
        try:
            response = requests.get(f"{self.base_url}/user/stats")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 사용자 통계 조회 성공: {data['user_id']}")
                return True
            else:
                print(f"❌ 사용자 통계 조회 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 사용자 통계 조회 오류: {e}")
            return False
    
    def test_admin_system_stats(self):
        """관리자 시스템 통계 API 테스트"""
        print("🧪 관리자 시스템 통계 API 테스트")
        try:
            response = requests.get(
                f"{self.base_url}/admin/system_stats",
                params={"admin_key": self.admin_key}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 시스템 통계 조회 성공")
                print(f"   - 총 문서 수: {data['database']['total_documents']}")
                print(f"   - 총 청크 수: {data['database']['total_chunks']}")
                print(f"   - 고유 사용자 수: {data['database']['unique_users']}")
                return True
            else:
                print(f"❌ 시스템 통계 조회 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 시스템 통계 조회 오류: {e}")
            return False
    
    def test_admin_all_users(self):
        """관리자 모든 사용자 조회 API 테스트"""
        print("🧪 관리자 모든 사용자 조회 API 테스트")
        try:
            response = requests.get(
                f"{self.base_url}/admin/all_users",
                params={"admin_key": self.admin_key}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 모든 사용자 조회 성공")
                print(f"   - 총 사용자 수: {data['total_users']}")
                return True
            else:
                print(f"❌ 모든 사용자 조회 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 모든 사용자 조회 오류: {e}")
            return False
    
    def test_document_list(self):
        """문서 목록 API 테스트"""
        print("🧪 문서 목록 API 테스트")
        try:
            response = requests.get(f"{self.base_url}/documents")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 문서 목록 조회 성공: {len(data['documents'])}개 문서")
                return True
            else:
                print(f"❌ 문서 목록 조회 실패: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 문서 목록 조회 오류: {e}")
            return False
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 N_GPT 멀티유저 시스템 테스트 시작")
        print("=" * 50)
        
        tests = [
            ("사용자 통계", self.test_user_stats),
            ("문서 목록", self.test_document_list),
            ("관리자 시스템 통계", self.test_admin_system_stats),
            ("관리자 모든 사용자 조회", self.test_admin_all_users),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                print()
            except Exception as e:
                print(f"❌ {test_name} 테스트 중 예외 발생: {e}")
                print()
        
        print("=" * 50)
        print(f"🎯 테스트 결과: {passed}/{total} 통과")
        
        if passed == total:
            print("🎉 모든 테스트가 성공했습니다!")
        else:
            print(f"⚠️  {total - passed}개 테스트가 실패했습니다.")
        
        return passed == total

def main():
    """메인 실행 함수"""
    print("N_GPT 멀티유저 시스템 테스트")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 서버가 실행 중인지 확인
    try:
        response = requests.get("http://localhost:8000/")
        if response.status_code != 200:
            print("❌ 서버가 실행되고 있지 않습니다. python main.py로 서버를 먼저 시작하세요.")
            return
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        print("서버가 실행되고 있는지 확인하세요: python main.py")
        return
    
    tester = NGPTTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
