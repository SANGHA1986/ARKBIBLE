@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [ARK] 현재 폴더: %CD%
echo.

REM python이 PATH에 없으면 py 런처 사용
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  set PY=python
) else (
  where py >nul 2>&1
  if %ERRORLEVEL%==0 (
    set PY=py -3
  ) else (
    echo [오류] python 을 찾을 수 없습니다.
    echo Python 설치 후 "Add python.exe to PATH" 를 체크하거나,
    echo 이 창에서 아래처럼 전체 경로로 실행하세요.
    echo   C:\Users\Administrator\Python311\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
    pause
    exit /b 1
  )
)

echo [ARK] 사용 인터프리터: %PY%
%PY% -c "import uvicorn; print('[ARK] uvicorn OK', uvicorn.__version__)" 2>nul
if errorlevel 1 (
  echo [오류] uvicorn 이 없습니다. 설치합니다...
  %PY% -m pip install uvicorn fastapi sqlalchemy
)

echo.
echo [ARK] 백엔드 시작: http://127.0.0.1:8000
echo 이 창을 닫지 마세요. 중지: Ctrl+C
echo.
%PY% -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
