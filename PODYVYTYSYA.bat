@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KARTA - podyvytysya
set PY=py -3
%PY% --version >nul 2>&1 || set PY=python

if not exist site\kyiv.html (
  echo.
  echo Karty shche nemae. Spershu zapustit 3-MAP.bat
  echo.
  pause
  exit /b 1
)

echo.
echo ========================================
echo   KARTA VIDKRYVAETSYA V BRAUZERI
echo ========================================
echo.
echo Adresa: http://127.0.0.1:8777/
echo.
echo Prosto vidkryty fayl podviynym klatsannyam ne mozhna:
echo panel rishen tyagne sudovi spravy susidnim faylom,
echo a brauzer faylu z dysku takogo ne dozvolyae.
echo.
echo Shchob zakryty - zakryyte tse vikno.
echo.

start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8777/"
%PY% -m http.server 8777 --directory site
