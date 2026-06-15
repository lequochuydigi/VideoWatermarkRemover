@echo off
:: Di chuyen vao thu muc chua file bat nay (quan trong!)
cd /d "%~dp0"
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
    echo.
    echo  Khi cai dat nho tick "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Tim thay: %%v
echo.

:: --- Tao moi truong ao neu chua co ---
if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] Dang tao moi truong ao .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo.
        echo  [LOI] Khong the tao virtual environment.
        pause
        exit /b 1
    )
    echo  Tao xong!
    echo.
)

:: --- Cap nhat / cai thu vien ---
echo  [2/3] Dang cai dat thu vien (lan dau mat 1-3 phut)...
echo.
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  ==========================================
    echo  [LOI] Cai dat thu vien that bai!
    echo  Kiem tra ket noi internet roi thu lai.
    echo  ==========================================
    pause
    exit /b 1
)

echo.
echo  [3/3] Dang khoi dong server...

:: Mo trinh duyet sau 4 giay
start "" /B cmd /C "timeout /t 4 >nul && start http://localhost:5000"

echo.
echo  ==========================================
echo   >>> http://localhost:5000
echo   >>> Nhan Ctrl+C de dung
echo  ==========================================
echo.

:: Chay server - hien thi loi truc tiep ra cua so nay
.venv\Scripts\python app.py

:: Neu den duoc day la server bi dung
echo.
echo  ==========================================
echo  Server da dung. Xem loi o tren neu co.
echo  ==========================================
pause
