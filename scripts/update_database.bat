@echo off
setlocal
title DRASS - update database
cd /d "%~dp0.."
echo DRASS database update
echo Folder: %CD%
echo.
if not exist ".venv\Scripts\python.exe" goto novenv

echo [1/3] Backing up the database...
".venv\Scripts\python.exe" scripts\backup_now.py
if errorlevel 1 goto backupfail

echo.
echo [2/3] Aligning roles, workflow and tables with the manuscript (type YES when asked)...
".venv\Scripts\python.exe" scripts\align_database_to_manuscript.py
if errorlevel 1 goto fail

echo.
echo [3/3] Re-indexing the archived studies for search (can take a few minutes)...
".venv\Scripts\python.exe" scripts\rebuild_embeddings.py all

echo.
echo DONE. Start the server again. If a WARNING about the Head Librarian was printed, tick "Head Librarian" on a Library Staff account (Administrator > Users).
goto end

:novenv
echo The .venv folder was not found in %CD%
echo Run this file from inside the DRASS project folder.
goto end

:backupfail
echo.
echo BACKUP FAILED - nothing was changed. Check that MySQL is running and that mysqldump works.
goto end

:fail
echo.
echo FAILED or cancelled - read the message above. Nothing after this step was run.

:end
echo.
pause
