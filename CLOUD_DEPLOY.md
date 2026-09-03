# GitHub Actions + Streamlit Community Cloud

## GitHub Actions secrets

Repository **Settings → Secrets and variables → Actions → New repository secret**에서 등록합니다.

- `NAVER_WORKS_SMTP_USER`: 네이버웍스 전체 메일 주소
- `NAVER_WORKS_SMTP_APP_PASSWORD`: 네이버웍스의 외부 앱 비밀번호
- `REPORT_RECIPIENTS`: 수신자 메일 주소를 쉼표로 연결한 목록

외부 앱 비밀번호가 아직 없으면 순위 수집과 대시보드 업데이트는 정상 진행되고 메일만 건너뜁니다.

## Streamlit Community Cloud

- Repository: 이 프로젝트의 GitHub 저장소
- Branch: `main`
- Main file path: `dashboard.py`

GitHub Actions가 매일 한국 시간 오전 10시에 CSV를 갱신해 저장소에 커밋하면 Streamlit Cloud가 새 커밋을 자동 반영합니다.
