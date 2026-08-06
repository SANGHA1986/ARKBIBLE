@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [ARK] 프론트 시작: http://localhost:3000
echo 이 창을 닫지 마세요.
npm run dev
pause
