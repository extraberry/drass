@echo off
REM DRASS backup: database dump + research files + manifest, into BACKUP_DIR (.env). Use --scheduled from Task Scheduler.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" ( echo .venv not found. Run this from the DRASS project folder. & pause & exit /b 1 )
".venv\Scripts\python.exe" scripts\backup_now.py %*
if errorlevel 1 ( echo. & echo BACKUP FAILED - see the message above. & if "%1"=="" pause & exit /b 1 )
if "%1"=="" pause
