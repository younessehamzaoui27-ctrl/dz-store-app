@echo off
chcp 65001 > nul
title DZ COD Engine - التثبيت والتشغيل التلقائي
color 0A

echo ======================================================================
echo           DZ COD Engine Pro - التثبيت والتشغيل التلقائي بنقرة واحدة
echo ======================================================================
echo.

:: 1. التحقق من وجود بايثون
echo [1/3] فحص بيئة العمل والنظام...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [!] بايثون غير مثبت في هذا الحاسوب.
    echo [*] جاري تحميل وتثبيت بايثون تلقائياً... يرجى الانتظار ثوانٍ معدودة.
    echo.
    
    :: تحميل مثبت بايثون الرسمي الصامت
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $wc = New-Object System.Net.WebClient; $wc.DownloadFile('https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe', 'python_installer.exe')"
    
    echo [*] جاري التثبيت التلقائي لبايثون في جهازك...
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del python_installer.exe
    
    echo [+] تم تثبيت بايثون بنجاح في جهازك!
) else (
    echo [+] بايثون متوفر في جهازك وجاهز للعمل.
)

echo.
echo [2/3] فحص وتثبيت المكتبات المطلوبة أوتوماتيكياً...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet fastapi uvicorn httpx pydantic

echo.
echo [3/3] جاري تشغيل المنصة وفتح لوحة التحكم تلقائياً...
echo.
echo ======================================================================
echo   المنصة تعمل بنجاح!
echo   - صفحة البيع للزبائن:   http://localhost:8000/
echo   - لوحة تحكم التاجر:      http://localhost:8000/admin
echo ======================================================================
echo.

:: فتح لوحة التحكم في المتصفح تلقائياً
start http://localhost:8000/admin

:: تشغيل السيرفر
python -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
