@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo  ARK Open LEXICON / Etymology
echo  Strong's (PD) + STEP TBESG/TBESH (CC BY)
echo  + Sefaria samples (Mixed, meta kept)
echo  Duplicates: skipped by content_hash
echo ========================================
echo.
python -u collect_open_lexicons.py --full
echo.
echo Done. Press any key to close.
pause >nul
