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

:: --- Kiem tra Python ---
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [LOI] Khong tim thay Python!
    echo.
    echo  Tai Python 3.12 tai: https://www.python.org/downloads/
    echo  Khi cai nho tick "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Tim thay: %%v

:: Canh bao nhe neu Python 3.13+
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
    for /f "tokens=1,2 delims=." %%a in ("%%v") do (
        if %%a GEQ 3 if %%b GEQ 13 (
            echo  [CANH BAO] Python %%v - neu gap loi cai dat thi thu Python 3.12
        )
    )
)
echo.

:: --- Tao moi truong ao ---
if not exist ".venv\Scripts\python.exe" (
    echo  [1/3] Tao moi truong ao .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [LOI] Khong the tao .venv
        pause
        exit /b 1
    )
    echo  Xong!
    echo.
)

:: --- Cai thu vien ---
echo  [2/3] Dang cai dat thu vien (lan dau mat 1-3 phut)...
echo.
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [LOI] Cai dat thu vien that bai.
    echo  Kiem tra ket noi internet roi xoa .venv va thu lai.
    pause
    exit /b 1
)

echo.
echo  Cai dat xong!
echo.

:: --- Them ngoai le tuong lua Windows (tranh bi chan) ---
echo  [2.5] Them ngoai le tuong lua cho Python...
netsh advfirewall firewall delete rule name="WatermarkEraser-Python" >nul 2>&1
netsh advfirewall firewall add rule name="WatermarkEraser-Python" dir=in action=allow program="%CD%\.venv\Scripts\python.exe" enable=yes >nul 2>&1
echo  Xong!
echo.

:: --- Khoi dong server ---
echo  [3/3] Dang khoi dong server...
echo.

:: Mo trinh duyet sau 4 giay (dung 127.0.0.1 thay vi localhost)
start "" /B cmd /C "timeout /t 4 >nul && start http://127.0.0.1:8080"

echo  ==========================================
echo   >>> Dang chay tai: http://127.0.0.1:8080
echo   >>> Nhan Ctrl+C de dung server
echo  ==========================================
echo.
echo  [Nhat ky server]
echo  ----------------------------------------

.venv\Scripts\python app.py

:: Server da dung (crash hoac Ctrl+C)
echo.
echo  ==========================================
echo  Server da dung.
echo.
echo  Neu gap loi, chup anh man hinh gui ho tro.
echo  Neu muon chay lai: double-click run.bat
echo  ==========================================
pause
