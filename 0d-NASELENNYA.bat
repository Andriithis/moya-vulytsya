@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 0d - naselennya
py -3 src\step0d_population.py 2>nul || python src\step0d_population.py
echo.
pause
