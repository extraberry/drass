@echo off
cd /d "%~dp0"
start "DRASS server" cmd /k ".venv\Scripts\python.exe -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000"
timeout /t 6 >nul
.venv\Scripts\python.exe client\main.py
