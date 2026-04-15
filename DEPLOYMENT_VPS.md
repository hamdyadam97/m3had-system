# دليل النشر على VPS (Hostinger) باستخدام Docker

> هذا الدليل يشرح خطوات رفع مشروع **Institute Management** على VPS Linux (Ubuntu 22.04+) في Hostinger باستخدام **Docker + Docker Compose + Nginx + Let's Encrypt SSL**.

---

## 📋 المتطلبات

- VPS Ubuntu 22.04 LTS (أو أحدث)
- Docker & Docker Compose مثبتين
- دومين موجه للـ VPS IP (A Record)
- Image موجود على Docker Hub: `hamdyadam/institute-management:latest`

---

## 🚀 خطوات النشر

### 1️⃣ إعداد السيرفر (Ubuntu)

اتصل بالسيرفر عبر SSH:

```bash
ssh root@YOUR_SERVER_IP
```

حدّث النظام وثبّت Docker:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common git

# تثبيت Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# تفعيل Docker
sudo systemctl enable docker
sudo systemctl start docker

# تثبيت Docker Compose (Plugin مدمج مع docker-ce أو legacy)
docker compose version || sudo apt install -y docker-compose
```

---

### 2️⃣ نسخ ملفات المشروع على السيرفر

#### الطريقة أ: Clone من GitHub (مُوصى بها)

```bash
cd /opt
sudo git clone https://github.com/hamdyadam/institute_management.git institute
sudo chown -R $USER:$USER institute
cd institute
```

#### الطريقة ب: رفع الملفات يدوياً

من جهازك المحلي:

```bash
scp -r . root@YOUR_SERVER_IP:/opt/institute
ssh root@YOUR_SERVER_IP
chown -R $USER:$USER /opt/institute
```

---

### 3️⃣ إعداد ملف البيئة الإنتاجية

```bash
cd /opt/institute
cp .env.prod.example .env.prod
nano .env.prod
```

**أهم المتغيرات اللي لازم تعدلها:**

```env
SECRET_KEY=your-50-char-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,localhost,127.0.0.1

# PostgreSQL
DB_NAME=institute_db
DB_USER=institute_user
DB_PASSWORD=very-strong-db-password

# Superuser auto-creation (اختياري)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@yourdomain.com
DJANGO_SUPERUSER_PASSWORD=very-strong-admin-password

# Brevo Email
EMAIL_HOST_USER=your-brevo-email@smtp-brevo.com
EMAIL_HOST_PASSWORD=your-brevo-key
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# WhatsApp
WHATSAPP_API_TOKEN=your-token
WHATSAPP_INSTANCE_ID=your-instance-id

# Celery/Redis
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

> ⚠️ **نصيحة أمنية:** غيّر `SECRET_KEY` وكلمات المرور كلها. استخدم مولد عشوائي للـ Secret Key.

---

### 4️⃣ تعديل إعدادات Nginx و SSL

افتح ملف `init-letsencrypt.sh` وعدل أول سطرين:

```bash
nano init-letsencrypt.sh
```

```bash
DOMAINS=("yourdomain.com" "www.yourdomain.com")
EMAIL="admin@yourdomain.com"
```

احفظ وأغلق (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

### 5️⃣ تشغيل Docker Compose (بدون SSL أولاً)

```bash
cd /opt/institute
sudo docker compose -f docker-compose.prod.yml up -d
```

هذا هيشغّل:
- **PostgreSQL**
- **Redis**
- **Django Web**
- **Celery Worker**
- **Celery Beat**
- **Nginx**
- **Certbot (للتجديد التلقائي)**

---

### 6️⃣ الحصول على شهادة SSL (Let's Encrypt)

```bash
cd /opt/institute
chmod +x init-letsencrypt.sh
sudo ./init-letsencrypt.sh
```

السكريبت هيعمل:
1. ينشئ شهادة مؤقتة (dummy)
2. يشغّل Nginx
3. يطلب الشهادة الحقيقية من Let's Encrypt
4. يحدّث ملف `nginx/nginx.conf` بالنطاق
5. يعيد تحميل Nginx

> ✅ تأكد إن الدومين موجه للـ VPS IP عشان السكريبت ينجح.

---

### 7️⃣ التحقق من النشر

افتح المتصفح وادخل على:

```
https://yourdomain.com
```

لو كل حاجة مظبوطة، هيتفتح المشروع.

---

## 🔍 أمر مفيدة للتحكم

### عرض حالة الخدمات
```bash
sudo docker compose -f docker-compose.prod.yml ps
```

### عرض اللوجز
```bash
# كل الخدمات
sudo docker compose -f docker-compose.prod.yml logs -f

# خدمة معينة
sudo docker compose -f docker-compose.prod.yml logs -f web
sudo docker compose -f docker-compose.prod.yml logs -f nginx
sudo docker compose -f docker-compose.prod.yml logs -f celery
```

### إعادة تشغيل خدمة
```bash
sudo docker compose -f docker-compose.prod.yml restart web
```

### إيقاف كل الخدمات
```bash
sudo docker compose -f docker-compose.prod.yml down
```

### إدخال أوامر Django داخل Container
```bash
sudo docker compose -f docker-compose.prod.yml exec web python manage.py migrate
sudo docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
sudo docker compose -f docker-compose.prod.yml exec web python manage.py shell
```

---

## 🔄 تحديث المشروع (Deploy Update)

لو عملت تعديلات ورفعت Image جديد على Docker Hub:

```bash
cd /opt/institute

# سحب آخر إصدار
sudo docker pull hamdyadam/institute-management:latest

# إعادة تشغيل الخدمات المعنية
sudo docker compose -f docker-compose.prod.yml up -d --no-deps --build web celery celery-beat

# عمل migrate (لو فيه تغييرات في الـ DB)
sudo docker compose -f docker-compose.prod.yml exec web python manage.py migrate --noinput

# جمع الملفات الثابتة (لو فيه static جديدة)
sudo docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

> 💡 **نصيحة:** لو بتستخدم GitHub Actions، ممكن ت automate الخطوات دي بالكامل.

---

## 🗄️ نسخ احتياطي للـ Database

### نسخ احتياطي
```bash
sudo docker compose -f docker-compose.prod.yml exec db pg_dump -U institute_user institute_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### استعادة
```bash
cat backup_file.sql | sudo docker compose -f docker-compose.prod.yml exec -T db psql -U institute_user -d institute_db
```

### نسخ احتياطي تلقائي يومي (Cron Job)
```bash
sudo crontab -e
```

أضف:
```cron
0 3 * * * cd /opt/institute && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U institute_user institute_db > /opt/backups/institute_$(date +\%Y\%m\%d_\%H\%M\%S).sql 2>/dev/null
```

---

## 🛠️ حل المشاكل الشائعة

### مشكلة: "502 Bad Gateway"
```bash
# تأكد إن web container شغال
sudo docker compose -f docker-compose.prod.yml ps
sudo docker compose -f docker-compose.prod.yml logs web
```

### مشكلة: "SSL Certificate not valid"
```bash
# تأكد إن certbot نجح
sudo docker compose -f docker-compose.prod.yml logs certbot

# جرب تشغيل السكريبت تاني
sudo ./init-letsencrypt.sh
```

### مشكلة: "Permission denied on media/static files"
```bash
sudo docker compose -f docker-compose.prod.yml exec web ls -la /app/staticfiles
sudo docker compose -f docker-compose.prod.yml exec web chown -R root:root /app/media
```

### مشكلة: "Celery not processing tasks"
```bash
sudo docker compose -f docker-compose.prod.yml logs celery
sudo docker compose -f docker-compose.prod.yml restart celery celery-beat
```

---

## 📞 دعم

لو واجهت أي مشكلة، افتح issue أو تواصل مع المطور.
