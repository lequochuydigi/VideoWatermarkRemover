@echo off
chcp 65001 >nul 2>&1
title Antigravity Watermark Eraser

echo.
echo  ==========================================
echo   Antigravity Watermark Eraser
echo  ==========================================
echo.

:: --- Kiem tra Python 3 ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [LOI] Khong tim thay Python!
    echo.
    echo  Vui long tai Python 3.10+ tai:
    echo    https://www.python.org/downloads/
    echo  Nho tick "Add Python to PATH" khi cai dat.
    echo.
    pause
    exit /b 1
)

:: --- Tao moi truong ao neu chua co ---
if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] Dang tao moi truong ao ^(.venv^)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [LOI] Khong the tao virtual environment.
        pause
        exit /b 1
    )
)

:: --- Cap nhat / cai thu vien ---
echo  [2/3] Dang kiem tra thu vien...
.venv\Scripts\pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [LOI] Cai dat thu vien that bai.
    echo  Thu chay thu cong: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: --- Mo trinh duyet sau 3 giay ---
echo  [3/3] Dang khoi dong server...
start "" /B cmd /C "timeout /t 3 >nul && start http://localhost:5000"

:: --- Chay server ---
echo.
echo  >>> Dang chay tai: http://localhost:5000
echo  >>> Nhan Ctrl+C de dung server.
echo.
.venv\Scripts\python app.py

echo.
echo  Server da dung. Nhan phim bat ky de dong.
pause >nul
