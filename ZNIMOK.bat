@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Eksport znimka dlya GitHub
py -3 src\export_snapshot.py 2>nul || python src\export_snapshot.py
