@echo off
setlocal
cd /d "%~dp0"

echo [1/2] GitHub에서 최신 랭킹 누적 데이터를 확인합니다...
git -c safe.directory="%CD%" pull --rebase --autostash origin main
if errorlevel 1 (
    echo.
    echo 최신 데이터 동기화에 실패했습니다. 현재 PC에 저장된 데이터로 실행합니다.
    echo 인터넷 연결 또는 GitHub 로그인을 확인해 주세요.
)

echo.
echo [2/2] 컬러렌즈 대시보드를 실행합니다...
echo 브라우저가 자동으로 열리지 않으면 http://127.0.0.1:8501 을 여세요.
python -m streamlit run dashboard.py --server.port 8501

endlocal
