@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 2 - geokoduvannya
py -3 src\step2_geocode.py 2>nul || python src\step2_geocode.py
echo.
pause
