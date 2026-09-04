@echo off
chcp 65001 > nul
cd /d "%~dp0"
title ONOVLENNYA KARTY
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python

echo.
echo ========================================
echo   ONOVLENNYA KARTY - vsi kroky pidryad
echo ========================================
echo.
echo [1/3] Zavantazhennya novyh rishen...
%PY% src\step1_download.py
if errorlevel 1 goto err

echo.
echo [2/3] Geokoduvannya...
%PY% src\step2_geocode.py
if errorlevel 1 goto err

echo.
echo [3/3] Zbirka karty...
%PY% src\step3_map.py
if errorlevel 1 goto err

echo.
echo === GOTOVO === kartu zibrano v papku site
echo Shchob podyvytysya - zapustit PODYVYTYSYA.bat
echo.
pause
exit /b 0

:err
echo.
echo !!! POMYLKA na odnomu z krokiv - dyvit'sya povidomlennya vyshche
echo.
pause
exit /b 1
