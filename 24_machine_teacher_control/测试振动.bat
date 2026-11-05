@echo off
rem Gamepad rumble feel test. This one DOES vibrate the pad. Nothing else.
chcp 65001 >nul
setlocal
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PYEXE%" set PYEXE=py
set PYTHONIOENCODING=utf-8
"%PYEXE%" "%~dp0tools\rumble_test.py" %*
echo.
pause
