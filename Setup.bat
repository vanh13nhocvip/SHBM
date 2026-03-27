@echo off
setlocal enabledelayedexpansion
title Cài đặt SHBM - All In One Setup

echo ======================================================
echo           SHBM - HỆ THỐNG TRÍCH XUẤT SIÊU DỮ LIỆU
echo                 HƯỚNG DẪN CÀI ĐẶT TỰ ĐỘNG
echo ======================================================
echo.

REM 1. Kiểm tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Không tìm thấy Python trong hệ thống.
    echo Vui lòng cài đặt Python 3.8 trở lên tại https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Đã tìm thấy Python.

REM 2. Tạo môi trường ảo (Virtual Environment)
if not exist "venv" (
    echo [INFO] Đang tạo môi trường ảo (venv)...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Không thể tạo môi trường ảo.
        pause
        exit /b 1
    )
    echo [OK] Đã tạo môi trường ảo thành công.
) else (
    echo [OK] Môi trường ảo đã tồn tại.
)

REM 3. Nâng cấp Pip và cài đặt thư viện
echo [INFO] Đang nâng cấp pip...
.\venv\Scripts\python.exe -m pip install --upgrade pip

if exist "requirements.txt" (
    echo [INFO] Đang cài đặt các thư viện cần thiết từ requirements.txt...
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [WARNING] Có lỗi xảy ra trong quá trình cài đặt thư viện.
    ) else (
        echo [OK] Đã cài đặt thư viện thành công.
    )
) else (
    echo [WARNING] Không tìm thấy file requirements.txt.
)

REM 4. Kiểm tra công cụ ngoại vi
echo [INFO] Kiểm tra công cụ bổ trợ (Poppler, Tesseract)...
if exist "src\tools\deps\poppler" (
    echo [OK] Tìm thấy Poppler nội bộ.
) else (
    echo [WARNING] Thiếu Poppler trong src\tools\deps\poppler.
)

if exist "src\tools\deps\tesseract" (
    echo [OK] Tìm thấy Tesseract nội bộ.
) else (
    echo [WARNING] Thiếu Tesseract trong src\tools\deps\tesseract.
)

echo.
echo ======================================================
echo CÀI ĐẶT HOÀN TẤT!
echo.
echo Để khởi chạy phần mềm, hãy chạy file: Run.bat
echo ======================================================
echo.
pause
