@echo off
chcp 65001 > nul
cd /d "%~dp0"
title KROK 4 - analitychnyy dvygun
echo Perevirka bibliotek...
py -3 -m pip install --quiet numpy scikit-learn 2>nul || python -m pip install --quiet numpy scikit-learn
echo.
py -3 src\step4_engine.py 2>nul || python src\step4_engine.py
echo.
pause
