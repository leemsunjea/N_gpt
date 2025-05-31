# CloudType 배포 가이드

CloudType 환경에서는 파일 시스템에 대한 쓰기 권한이 제한되어 있습니다. 다음 단계에 따라 N_GPT 애플리케이션을 배포하세요.

## 1. 파일 준비

다음 파일들을 CloudType에 배포하기 전에 이름을 변경하세요:

```bash
mv main.py.new main.py
mv Dockerfile.new Dockerfile
mv start.sh.new start.sh
```

## 2. 배포 확인 사항

배포 전에 다음 사항을 확인하세요:

1. Dockerfile에서 필요한 패키지가 모두 포함되어 있는지 확인
2. start.sh에 실행 권한이 부여되어 있는지 확인 (`chmod +x start.sh`)
3. 데이터베이스 연결 정보가 올바른지 확인

## 3. CloudType 환경 설정

CloudType 대시보드에서 다음 환경 변수를 설정하세요:

- `CLOUDTYPE_DEPLOYMENT`: 1
- `DB_USER`: root
- `DB_PASSWORD`: sunjea
- `DB_HOST`: svc.sel4.cloudtype.app
- `DB_PORT`: 30173
- `DB_NAME`: testdb

## 4. 로그 확인

배포 후 로그를 확인하여 애플리케이션이 올바르게 작동하는지 확인하세요.
발생하는 오류가 있다면 로그를 통해 추가적인 디버깅을 진행하세요.

## 5. 문제 해결

1. 파일 권한 문제: CloudType 환경에서는 `/tmp` 디렉토리를 사용하여 임시 파일을 저장합니다.
2. 패키지 설치 문제: Dockerfile에서 필요한 모든 패키지를 미리 설치하고, 실행 중 추가 설치를 피합니다.
3. favicon.ico 문제: 별도의 엔드포인트로 favicon 요청을 처리합니다.
