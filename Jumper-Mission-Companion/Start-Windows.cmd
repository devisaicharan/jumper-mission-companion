@echo off
setlocal
title Jumper Mission Companion
cd /d "%~dp0"
if not exist "windows_start.py" goto extracted
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
  set "PY_RUN=py -3.12"
  goto run
)
py -3.13 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
  set "PY_RUN=py -3.13"
  goto run
)
python -c "import sys,struct; assert sys.version_info[:2] in [(3,12),(3,13)] and struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
  set "PY_RUN=python"
  goto run
)
echo Python 3.12 or 3.13, 64-bit, was not found.
echo Install it from https://www.python.org/downloads/windows/
echo Then double-click this launcher again.
pause
exit /b 1
:extracted
echo Extract the whole ZIP first, then open Start-Windows.cmd.
echo Do not run it from inside the ZIP preview.
pause
exit /b 1
:run
%PY_RUN% -u windows_start.py %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo If it failed, send windows-startup.log from this folder.
pause
exit /b %RESULT%
