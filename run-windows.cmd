@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
  echo Run the Windows setup commands in README.md first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
set "watcher_exit=%errorlevel%"
echo Watcher exited with code %watcher_exit%.
pause
exit /b %watcher_exit%
