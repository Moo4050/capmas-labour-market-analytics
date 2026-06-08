@echo off
echo ====================================
echo   CAPMAS Labour Market Portal
echo ====================================
echo.
echo [1] تثبيت المكتبات المطلوبة...
pip install -r requirements.txt
echo.
echo [2] تشغيل الموقع...
echo.
echo افتح المتصفح على: http://localhost:8000
echo.
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
