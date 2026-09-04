@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 2b - shar ryzykiv z OSM
py -3 src\step2b_risks.py 2>nul || python src\step2b_risks.py
echo.
pause
