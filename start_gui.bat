@echo off
cd /d "D:\Administrator\Desktop\echopype"
if errorlevel 1 (
    echo [ERROR] Cannot cd to project directory.
    echo Please check: D:\Administrator\Desktop\echopype
    pause
    exit /b 1
)
"D:\Program Files\Anaconda\python.exe" -m src.app
if errorlevel 1 (
    echo.
    echo [ERROR] Launch failed. Check:
    echo   1. D:\Program Files\Anaconda\python.exe exists
    echo   2. PySide6 + echopype installed in Anaconda
    pause
)
