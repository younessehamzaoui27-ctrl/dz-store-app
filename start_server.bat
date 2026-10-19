@echo off
chcp 65001 > nul
title DZ COD Engine - خادم المنصة والتطبيق
echo ========================================================
echo       DZ COD Engine - منصة التجارة الإلكترونية الجزائرية
echo ========================================================
echo.
echo جاري تشغيل السيرفر على http://localhost:8000 ...
echo صفحة الهبوط للزبائن:   http://localhost:8000/
echo لوحة تحكم التاجر:      http://localhost:8000/admin
echo.
echo اضغط Ctrl+C لإيقاف السيرفر في أي وقت.
echo ========================================================
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
