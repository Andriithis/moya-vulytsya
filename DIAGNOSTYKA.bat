@echo off
chcp 65001 > nul
cd /d "%~dp0"
title DIAGNOSTYKA - adresy
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   SKILKY REALNYH DTP MOZHNA POKAZATY
echo ========================================
echo.
echo Odna avariya daye bagato dokumentiv.
echo Rahuemo po SPRAVAH, a ne po dokumentah.
echo Ce zaimae blyzko 10 hvylyn.
echo.

%PY% src\diag_case.py 40696 60 > DIAGNOSTYKA_REZULTAT.txt 2>&1

echo.
type DIAGNOSTYKA_REZULTAT.txt
echo.
echo ========================================
echo   Rezultat u fayli DIAGNOSTYKA_REZULTAT.txt
echo   Nadishlit yogo Claude.
echo ========================================
echo.
pause
