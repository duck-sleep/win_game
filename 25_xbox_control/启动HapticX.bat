@echo off
rem HapticX 启动器 — 使用完整Python 3.13(含tkinter),无控制台窗口
set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe
if not exist "%PYEXE%" set PYEXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe
start "" "%PYEXE%" -B "D:\win_game_project\25_xbox_control\hapticx\app.py"
