@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 3 - zbirka karty
py -3 src\step3_map.py 2>nul || python src\step3_map.py
echo.
echo Shchob podyvytysya - zapustit PODYVYTYSYA.bat
echo.
pause
