# إعداد Celery + Redis للتذكيرات التلقائية

## 📋 المتطلبات

### 1. تثبيت Redis

**على Windows (بـ Docker - أسهل طريقة):**
```bash
docker-compose up -d redis
```

**على Windows (بدون Docker):**
1. حمل Redis من: https://github.com/tporadowski/redis/releases
2. شغل `redis-server.exe`

**على Linux:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 2. تثبيت الباكجات الجديدة

```bash
pip install -r requirements.txt
```

أو لو محتاج تثبيت يدوي:
```bash
pip install celery redis django-celery-beat django-celery-results
```

### 3. عمل migrations للـ Celery

```bash
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_results
```

---

## 🚀 تشغيل النظام

### الطريقة 1: سكريبت Windows جاهز (أسهل)

```bash
start_celery.bat
```

ده هيشغللك 3 نوافذ:
- Celery Worker
- Celery Beat (المجدول)
- Django Server

### الطريقة 2: يدوياً (3 ترمنالات)

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Celery Worker:**
```bash
celery -A institute_management worker -l info -P solo
```

**Terminal 3 - Celery Beat:**
```bash
celery -A institute_management beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Terminal 4 - Django:**
```bash
python manage.py runserver
```

---

## ⏰ إعداد التذكيرات التلقائية

### 1. افتح Django Admin
```
http://localhost:8000/admin/django_celery_beat/periodictask/
```

### 2. أضف Task جديد:
- **Name:** `Send Daily Reminders`
- **Task (registered):** `students.tasks.send_installment_reminders_task`
- **Enabled:** ✓
- **Interval:**
  - لو عايز كل يوم: `Interval` → `every 1 days`
  - لو عايز كل ساعة: `Interval` → `every 1 hours`
  - لو عايز وقت محدد: `Crontab` → `0 9 * * *` (الساعة 9 صباحاً)

### 3. احفظ (Save)

---

## 🧪 اختبار Celery

### اختبار بسيط:
```python
python manage.py shell
```

```python
from students.tasks import test_celery_task, send_installment_reminders_task

# اختبار سريع
test_celery_task.delay()

# إرسال التذكيرات يدوياً
send_installment_reminders_task.delay()
```

لو شفت في الـ Terminal بتاع Worker رسالة "Celery is working!" يبقى كل حاجة شغالة ✅

---

## 📊 مراقبة المهام

### في Django Admin:
- **Periodic Tasks:** `/admin/django_celery_beat/periodictask/`
- **Task Results:** `/admin/django_celery_results/taskresult/`

### في الـ Logs:
شوف ملف `logs/django.log` أو الـ Terminal بتاع الـ Worker

---

## 🔧 إعدادات متقدمة

### تغيير وقت التذكيرات
في `NotificationSettings` في الـ Admin:
- `reminder_2days_before`: إرسال تذكير قبل يومين
- `reminder_1day_before`: إرسال تذكير قبل يوم
- `reminder_on_due_date`: إرسال تذكير يوم الاستحقاق
- `send_overdue_notice`: إرسال إشعار التأخر

### تغيير Redis URL
لو Redis شغال على server تاني، ضيف في `.env`:
```
CELERY_BROKER_URL=redis://your-server:6379/0
CELERY_RESULT_BACKEND=redis://your-server:6379/0
```

---

## ❌ حل المشاكل الشائعة

### مشكلة: "Redis connection refused"
**الحل:** تأكد إن Redis شغال:
```bash
redis-cli ping
# لازم يرد: PONG
```

### مشكلة: "ModuleNotFoundError: No module named 'celery'"
**الحل:**
```bash
pip install celery redis django-celery-beat django-celery-results
```

### مشكلة: Tasks مش بتشتغل
**الحل:**
1. تأكد إن الـ Worker شغال
2. تأكد إن الـ Task مُسجل صح (شوف الـ logs)
3. جرب تشغل Task يدوياً من shell

---

## 📁 الملفات الجديدة

| الملف | الوصف |
|-------|-------|
| `institute_management/celery.py` | إعدادات Celery |
| `students/tasks.py` | المهام (Tasks) |
| `docker-compose.yml` | Docker setup للـ Redis |
| `start_celery.bat` | سكريبت تشغيل Windows |
| `CELERY_SETUP.md` | هذا الملف |

---

## 🎯 ملخص سريع للإنتاج (Production)

على VPS (مثل DigitalOcean/Hetzner):

```bash
# 1. نصب Redis
sudo apt install redis-server

# 2. شغل Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 3. نصب الباكجات
pip install -r requirements.txt

# 4. عمل migrations
python manage.py migrate

# 5. شغل Django (Systemd أو Gunicorn)
gunicorn institute_management.wsgi:application --bind 0.0.0.0:8000

# 6. شغل Celery Worker (في background)
celery -A institute_management worker -l info --detach

# 7. شغل Celery Beat (في background)
celery -A institute_management beat -l info --detach --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

أو استخدم **Supervisor** أو **PM2** لإدارة العمليات.
