@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo  ARK Open ALL (NOT Bible)
echo  Policy: COLLECT_POLICY.md (PD/CC0/CC BY only)
echo  1) Lexicon / etymology (Sefaria skipped)
echo  2) Materials / research / personal open
echo  Bible WEB: collect_gaps.bat
echo  KO PD 1961: collect_ko_pd_bible.py
echo ========================================
echo.
echo --- [1/2] Lexicon ---
python -u collect_open_lexicons.py --full
echo.
echo --- [2/2] Materials ---
python -u collect_open_materials.py
echo.
echo Done. Press any key to close.
pause >nul
