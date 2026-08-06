@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo  ARK Bible collect — GAPS (missing only)
echo  Skip: chapters already in DB
echo  Source: World English Bible (Public Domain)
echo ========================================
echo.
python -u collect_open_bible.py --gaps
echo.
echo Done. Press any key to close.
pause >nul
