@echo off
chcp 65001 > nul
cd /d "%~dp0"
title FABULY - vytyagy obstavyn
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   VYTYAGY OBSTAVYN Z RISHEN
echo ========================================
echo.
echo Kachae opys podiyi z kozhnogo rishennya:
echo koly, de i shcho stalosya. Bez yurydychnoyi
echo chastyny - vona odnakova i nichogo ne dodae.
echo.
echo Poryadok: spershu naygustishi adresy,
echo tobto fabuly problem zyavlyatsya pershymy.
echo.
echo Ce dovgo - blyzko 5-7 godyn na 68 tysyach.
echo Mozhna perervaty budy-koly (Ctrl+C abo zakryty vikno):
echo nastupnyi zapusk prodovzhyt z togo samogo mistsya.
echo.
pause

%PY% src\step1b_fabula.py

echo.
echo ========================================
echo   GOTOVO. Fayl data\fabuly.csv.gz
echo ========================================
echo.
pause
