@echo off
rem Sing Twinkle Twinkle Little Star on the pad. This one DOES vibrate the pad.
chcp 65001 >nul
setlocal
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PYEXE%" set PYEXE=py
set PYTHONIOENCODING=utf-8
"%PYEXE%" "%~dp0sing_star.py" %*
echo.
pause
