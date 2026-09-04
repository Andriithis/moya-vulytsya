@echo off
chcp 65001 > nul
cd /d "%~dp0"
title ROZVIDKA TEKSTIV
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   ROZVIDKA TEKSTIV RISHEN
echo ========================================
echo.
echo Kachae nevelyku vybirku rishen i dyvytsya,
echo shcho v nyh napysano: skilky vazhyt fabula
echo i chy nazvano tam lyudynu.
echo.
echo Nichogo ne zberigae v bazu.
echo Zaimae blyzko dvoh hvylyn.
echo.
pause

%PY% src\diag_fabula.py

echo.
echo ========================================
echo   Rezultat u fayli FABULA_REZULTAT.txt
echo   Nadishlit yogo Claude.
echo ========================================
echo.
pause
