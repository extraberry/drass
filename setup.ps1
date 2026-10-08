# DRASS setup (Windows PowerShell). Run:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"          # call python directly: avoids Activate.ps1 / pip.exe policy problems
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env - edit MYSQL_PASSWORD before continuing." -ForegroundColor Yellow; exit 0 }
foreach ($d in "storage\manuscripts","storage\companions","storage\temp","backups") { New-Item -ItemType Directory -Force $d | Out-Null }
& $py scripts\setup.py
& $py scripts\setup_db.py --demo
Write-Host "Done. Start the server with run_server.bat and the client with run_client.bat" -ForegroundColor Green
