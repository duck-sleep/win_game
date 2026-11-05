@echo off
rem Audio loopback probe launcher. Does NOT touch the gamepad. Makes NO sound.
chcp 65001 >nul
setlocal
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PYEXE%" set PYEXE=py
set PYTHONIOENCODING=utf-8
"%PYEXE%" "%~dp0tools\probe_audio.py" %*
echo.
pause
