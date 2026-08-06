@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo  ARK Bible collect — FULL (66 books)
echo  Scope: all OT/NT chapters in BOOKS list
echo  Skip: chapters already in DB (no re-download)
echo  Source: World English Bible (Public Domain)
echo  NOTE: papers / Strong / STEP are separate scripts
echo ========================================
echo.
python -u collect_open_bible.py --gaps
echo.
echo Done. Press any key to close.
pause >nul
