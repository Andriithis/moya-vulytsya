@echo off
chcp 65001 > nul
cd /d "%~dp0"
title PEREVIRKA ZBIRKY
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python
set PYTHONIOENCODING=utf-8

echo.
echo ========================================
echo   PEREVIRKA ZBIRKY KARTY
echo ========================================
echo.
echo Zbyraye try karty na zmenshenii testovii bazi
echo i kazhe, chy zminyvsya rezultat.
echo Spravzhnya baza dlya cyogo NE potribna.
echo.
echo Poryadok: pered pravkoyu zapustit z klyuchem --save,
echo pislya pravky - bez klyucha.
echo.

%PY% src\check_build.py %*

echo.
pause
