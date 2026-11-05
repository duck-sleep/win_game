@echo off
rem Launcher for the Machenike (NS mode) HapticX window. No console window.
setlocal
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe
if not exist "%PYEXE%" set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
start "HapticX-Machenike" /D "%~dp0hapticx_ns" "%PYEXE%" -B app.py
