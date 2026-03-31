# دليل النشر على السيرفر (Production)

## 📋 المتطلبات

- Ubuntu 22.04 LTS (موصى به)
- PostgreSQL 14+
- Redis 7+
- Python 3.11+
- Nginx
- Gunicorn

---

## 🚀 خطوات النشر

### 1️⃣ إعداد السيرفر

```bash
# تحديث النظام
sudo apt update && sudo apt upgrade -y

# تثبيت المتطلبات
sudo apt install -y python3-pip python3-venv python3-dev postgresql postgresql-contrib redis-server nginx git build-essential libpq-dev

# تفعيل Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

---

### 2️⃣ إعداد PostgreSQL

```bash
# الدخول لـ PostgreSQL
sudo -u postgres psql

# داخل PostgreSQL:
CREATE DATABASE institute_db;
CREATE USER institute_user WITH PASSWORD 'strong_password_here';
GRANT ALL PRIVILEGES ON DATABASE institute_db TO institute_user;
\q
```

---

### 3️⃣ نسخ المشروع

```bash
# إنشاء مجلد المشروع
sudo mkdir -p /var/www/institute
sudo chown $USER:$USER /var/www/institute
cd /var/www/institute

# نسخ المشروع (أو clone من Git)
git clone https://github.com/yourusername/institute_management.git .
# أو انسخ الملفات يدوياً
```

---

### 4️⃣ إعداد البيئة الافتراضية

```bash
cd /var/www/institute

# إنشاء venv
python3 -m venv venv
source venv/bin/activate

# تثبيت المتطلبات
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 5️⃣ ملف .env

```bash
nano /var/www/institute/.env
```

**محتوى الملف:**

```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL)
DB_NAME=institute_db
DB_USER=institute_user
DB_PASSWORD=strong_password_here
DB_HOST=localhost
DB_PORT=5432

# OR using DATABASE_URL:
# DATABASE_URL=postgres://institute_user:strong_password_here@localhost:5432/institute_db

# Email (Brevo)
EMAIL_HOST_USER=your-email@smtp-brevo.com
EMAIL_HOST_PASSWORD=your-brevo-smtp-key

# WhatsApp (UltraMsg)
WHATSAPP_API_TOKEN=your-ultramsg-token
WHATSAPP_INSTANCE_ID=your-instance-id

# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

### 6️⃣ عمل Migrations

```bash
cd /var/www/institute
source venv/bin/activate

# عمل migrations
python manage.py migrate

# جمع الملفات الثابتة
python manage.py collectstatic --noinput

# إنشاء Superuser
python manage.py createsuperuser
```

---

### 7️⃣ اختبار Gunicorn

```bash
cd /var/www/institute
source venv/bin/activate

# اختبار
python manage.py check --deploy

# تشغيل Gunicorn للاختبار
gunicorn --bind 0.0.0.0:8000 institute_management.wsgi:application

# Ctrl+C للإيقاف
```

---

### 8️⃣ إعداد Systemd Services

#### Gunicorn Service:

```bash
sudo nano /etc/systemd/system/institute-gunicorn.service
```

**المحتوى:**

```ini
[Unit]
Description=Institute Management Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/institute
ExecStart=/var/www/institute/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/var/www/institute/app.sock institute_management.wsgi:application

[Install]
WantedBy=multi-user.target
```

#### Celery Worker Service:

```bash
sudo nano /etc/systemd/system/institute-celery.service
```

**المحتوى:**

```ini
[Unit]
Description=Institute Management Celery Worker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/institute
ExecStart=/var/www/institute/venv/bin/celery -A institute_management worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Celery Beat Service:

```bash
sudo nano /etc/systemd/system/institute-celery-beat.service
```

**المحتوى:**

```ini
[Unit]
Description=Institute Management Celery Beat
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/institute
ExecStart=/var/www/institute/venv/bin/celery -A institute_management beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

**تفعيل الخدمات:**

```bash
sudo systemctl daemon-reload
sudo systemctl start institute-gunicorn
sudo systemctl enable institute-gunicorn
sudo systemctl start institute-celery
sudo systemctl enable institute-celery
sudo systemctl start institute-celery-beat
sudo systemctl enable institute-celery-beat
```

---

### 9️⃣ إعداد Nginx

```bash
sudo nano /etc/nginx/sites-available/institute
```

**المحتوى:**

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/institute;
    }
    
    location /media/ {
        root /var/www/institute;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/institute/app.sock;
    }
}
```

**تفعيل:**

```bash
sudo ln -s /etc/nginx/sites-available/institute /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

---

### 🔟 SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## ✅ التحقق من النشر

```bash
# حالة الخدمات
sudo systemctl status institute-gunicorn
sudo systemctl status institute-celery
sudo systemctl status institute-celery-beat
sudo systemctl status nginx
sudo systemctl status redis-server

# لوغز الأخطاء
sudo journalctl -u institute-gunicorn
sudo journalctl -u institute-celery
```

---

## 🔄 تحديث المشروع

```bash
cd /var/www/institute
source venv/bin/activate

# سحب التحديثات
git pull

# تحديث المتطلبات
pip install -r requirements.txt

# عمل migrations
python manage.py migrate

# جمع الملفات الثابتة
python manage.py collectstatic --noinput

# إعادة تشغيل الخدمات
sudo systemctl restart institute-gunicorn
sudo systemctl restart institute-celery
sudo systemctl restart institute-celery-beat
```

---

## 🗄️ نسخ احتياطي للـ Database

```bash
# نسخ احتياطي
sudo -u postgres pg_dump institute_db > backup_$(date +%Y%m%d_%H%M%S).sql

# استعادة
sudo -u postgres psql institute_db < backup_file.sql
```

---

## 🛠️ حل المشاكل الشائعة

### مشكلة: "Permission denied"
```bash
sudo chown -R www-data:www-data /var/www/institute
sudo chmod -R 755 /var/www/institute
```

### مشكلة: "Static files not found"
```bash
python manage.py collectstatic --noinput
sudo systemctl restart institute-gunicorn
```

### مشكلة: "Database connection failed"
```bash
sudo systemctl status postgresql
sudo -u postgres psql -c "\du"  # التحقق من المستخدمين
```

---

## 📞 دعم

لو واجهت مشاكل، افتح issue على GitHub أو تواصل مع المطور.
