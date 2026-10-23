우리동네아이스크림 - 테스트 배포 준비 파일

중요: 이 패키지는 웹 배포 테스트용입니다. 실제 고객 주문을 받기 전에는 CSRF 방어, 로그인 시도 제한, 개인정보 처리방침, 주문/배송 운영 절차, 백업 및 결제 연동을 추가 점검해야 합니다.

Render 설정(유료 웹 서비스 + Persistent Disk 권장):
- Root Directory: our-neighborhood-icecream-update (저장소 루트에 이 폴더 내용만 올렸다면 비워 둠)
- Build Command: pip install -r requirements.txt
- Start Command: gunicorn wsgi:app
- Environment variables:
  ICE_ADMIN_PASSWORD = 직접 만든 길고 고유한 관리자 비밀번호
  ICE_SECRET_KEY = 충분히 긴 무작위 비밀 문자열
  ICE_DB_PATH = /var/data/ice_neighborhood.db
- Disk mount path: /var/data
- DB 파일은 GitHub에 올리지 말 것. 이 배포는 새 DB를 만들므로 기존 상품/주문 데이터는 자동 이전되지 않습니다.

기본값 change-this-password 및 change-this-secret-key를 실제 운영에 사용하지 마세요. 비밀값을 GitHub 저장소에 쓰지 말고 Render 대시보드의 Environment에서 설정하세요.
