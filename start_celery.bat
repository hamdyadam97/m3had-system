@echo off
chcp 65001 >nul
echo ==========================================
echo    نظام إدارة المعاهد - تشغيل Celery
echo ==========================================
echo.

REM Check if Redis is running
redis-cli ping >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Redis مش شغال!
    echo.
    echo عايز تشغل Redis بالـ Docker؟
    echo اكتب: docker-compose up -d redis
    echo.
    echo لو مش عندك Docker، حمل Redis من:
    echo https://github.com/tporadowski/redis/releases
    echo.
    pause
    exit /b 1
)

echo [OK] Redis شغال ✓
echo.

REM Navigate to project directory
cd /d "%~dp0"

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment مش موجود!
    pause
    exit /b 1
)

echo [1/3] تشغيل Celery Worker...
echo.
start "Celery Worker" cmd /k "title Celery Worker && celery -A institute_management worker -l info -P solo"

echo [2/3] تشغيل Celery Beat (المجدول)...
echo.
start "Celery Beat" cmd /k "title Celery Beat && celery -A institute_management beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"

echo [3/3] تشغيل Django...
echo.
start "Django Server" cmd /k "title Django Server && python manage.py runserver"

echo.
echo ==========================================
echo    تم تشغيل كل الخدمات!
echo ==========================================
echo.
echo الخدمات الشغالة:
echo   • Django:      http://localhost:8000
echo   • Redis:       redis://localhost:6379
echo   • Celery:      شغال في الخلفية
echo.
pause
