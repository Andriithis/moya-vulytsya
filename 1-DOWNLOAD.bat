@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 1 - zavantazhennya tekstiv
py -3 src\step1_download.py 2>nul || python src\step1_download.py
echo.
pause
