@echo off
chcp 65001 > nul
cd /d "%~dp0"
title PERERAHUNOK ADRES
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   PERERAHUNOK ADRES
echo ========================================
echo.
echo Shcho bude:
echo   1. Zrobyt rezervnu kopiyu bazy
echo   2. Znime zapysy, de stoyala adresa sudu
echo   3. Perezavantazhyt yih z vypravlenym kodom
echo   4. Geokoduye novi adresy
echo.
echo Ce zaimae blyzko godyny. Mozhna zgornuty vikno.
echo Yakshcho perervaty - prohres zberezhetsya.
echo.
pause

echo.
echo [0/3] Rezervna kopiya...
if exist data\events.db copy /Y data\events.db data\events_backup.db > nul
if exist data\events.csv.gz copy /Y data\events.csv.gz data\events_backup.csv.gz > nul
echo     data\events_backup.db

echo.
echo [1/3] Teksty rishen i adresy...
%PY% src\step1_download.py
if errorlevel 1 goto err

echo.
echo [2/3] Geokoduvannya...
%PY% src\step2_geocode.py
if errorlevel 1 goto err

echo.
echo ========================================
echo   GOTOVO
echo.
echo   Teper zavantazhte fayl
echo   data\events.csv.gz
echo   na GitHub u papku data (zaminyty).
echo   Potim zapustit workflow v Actions
echo   z galochkoyu retrain_risk.
echo ========================================
echo.
pause
exit /b 0

:err
echo.
echo POMYLKA. Rezervna kopiya tut: data\events_backup.db
echo Shchob vidkotyty - pereimenuyte yiyi na events.db
pause
