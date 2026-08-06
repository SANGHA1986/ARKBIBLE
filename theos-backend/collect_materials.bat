@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo  ARK Open MATERIALS (papers / research)
echo  Protestant / Catholic / Orthodox / Personal
echo  Only PD / CC / user-open JSON
echo  Drop files in: data_open_materials\
echo  Duplicates: skipped (title+author)
echo ========================================
echo.
python -u collect_open_materials.py
echo.
echo Done. Press any key to close.
pause >nul
