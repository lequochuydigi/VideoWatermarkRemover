@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1
title Antigravity Watermark Eraser Compiler

echo.
echo  ==========================================
echo   Antigravity Watermark Eraser Compiler
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+.
    pause
    exit /b 1
)

:: Create Virtual Environment if not exists
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment ^(.venv^) ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
    echo.
)

:: Install/Upgrade dependencies
echo [2/4] Installing requirements and PyInstaller ...
.venv\Scripts\python -m pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)
echo.

:: Build Executable
echo [3/4] Compiling application using PyInstaller ...
echo.
.venv\Scripts\pyinstaller --clean --onefile --noconsole --add-data "templates;templates" --add-data "static;static" --collect-all imageio_ffmpeg --name "AntigravityWatermarkEraser" app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Compilation failed. Check the error messages above.
    pause
    exit /b 1
)
echo.

:: Copy output to root
echo [4/4] Copying executable to root directory ...
if exist "dist\AntigravityWatermarkEraser.exe" (
    copy /Y "dist\AntigravityWatermarkEraser.exe" "AntigravityWatermarkEraser.exe" >nul
    echo.
    echo  ==========================================
    echo   BUILD SUCCESSFUL!
    echo   Executable: E:\Antigravity\watermark_remover\AntigravityWatermarkEraser.exe
    echo  ==========================================
) else (
    echo [ERROR] Executable not found in dist folder.
)
echo.
pause
