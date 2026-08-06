@echo off
chcp 65001 >nul
echo === ARK 테스트 서버 시작 ===
echo.

cd /d D:\AUTOBOT\ARKPC\theos-backend

echo [1/3] 포트 8000 / 3000 정리...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/3] 백엔드 시작 (http://127.0.0.1:8000) ...
start "ARK-Backend" cmd /k "cd /d D:\AUTOBOT\ARKPC\theos-backend && set ARK_OPEN_BETA=1 && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [3/3] 프론트 시작 (http://localhost:3000) ...
start "ARK-Frontend" cmd /k "cd /d D:\AUTOBOT\ARKPC\theos-web && npm run dev"

echo.
echo 준비되면 브라우저에서 여세요:
echo   http://localhost:3000
echo.
echo 홈에서 「논문」「인물」「장소」「교리」를 눌러 확인하세요.
echo Ctrl+Shift+R 로 강제 새로고침 권장.
echo.
pause
