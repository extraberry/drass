@echo off
setlocal
title DRASS - reset for demo
cd /d "%~dp0.."
echo DRASS demo reset
echo Folder: %CD%
echo.
if not exist ".venv\Scripts\python.exe" goto novenv
echo Stop the server first (close its window), then continue.
echo.
echo   Press 1 = reset WITH the sample research (the archive already has studies to search)
echo   Press 2 = reset EMPTY (you submit, verify and archive live during the demo)
echo.
choice /c 12 /n /m "Your choice (1 or 2): "
if errorlevel 2 goto empty
".venv\Scripts\python.exe" scripts\reset_demo.py
goto end
:empty
".venv\Scripts\python.exe" scripts\reset_demo.py --empty
goto end
:novenv
echo The .venv folder was not found in %CD%
echo Run this file from inside the DRASS project folder.
:end
echo.
pause
