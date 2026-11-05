@echo off
rem Live audio -> HD rumble. Play music first, then run this. This one DOES vibrate the pad.
chcp 65001 >nul
setlocal
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
if not exist "%PYEXE%" set PYEXE=py
set PYTHONIOENCODING=utf-8
echo Close Steam/BetterJoy/DS4Windows first. Play some music, then press any key.
pause >nul
"%PYEXE%" "%~dp0live_a2h.py" --print %*
echo.
pause
