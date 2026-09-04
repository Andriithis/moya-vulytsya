@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 2c - merezhevyy analiz
set /p ST=Nazva vulytsi dlya perevirky (abo Enter): 
py -3 src\step2c_network.py "%ST%" 2>nul || python src\step2c_network.py "%ST%"
echo.
pause
