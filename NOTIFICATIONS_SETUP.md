# إعدادات الإشعارات والتنبيهات

## 📧 إعدادات الإيميل (Gmail SMTP)

### 1. تفعيل المصادقة الثنائية (2FA) على حساب Gmail
1. اذهب إلى [myaccount.google.com](https://myaccount.google.com)
2. الأمان ← المصادقة الثنائية ← فعلها

### 2. إنشاء App Password
1. الأمان ← كلمات مرور التطبيقات
2. اختر "تطبيق آخر (مخصص)"
3. سمّه "Django App"
4. انسخ الباسورد اللي هيطلع

### 3. الإعدادات في ملف `.env` أو متغيرات البيئة

```bash
# الإيميل
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
```

### أو في `settings.py` مباشرة (غير مستحسن للإنتاج)
```python
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

---

## 💬 إعدادات WhatsApp

### الخيار 1: UltraMsg (موصى به)
1. سجل في [ultramsg.com](https://ultramsg.com)
2. أنشئ instance واحصل على:
   - Instance ID
   - Token
3. ضبط الإعدادات:

```bash
WHATSAPP_PROVIDER=ultramsg
WHATSAPP_API_TOKEN=your-token
WHATSAPP_INSTANCE_ID=your-instance-id
```

### الخيار 2: CallMeBot (مجاني)
1. ارسل رسالة على واتساب لـ `+34 603 21 63 93` تتضمن `I allow callmebot to send me messages`
2. استلم الـ API Key
3. ضبط الإعدادات:

```bash
WHATSAPP_PROVIDER=callmebot
WHATSAPP_API_TOKEN=your-api-key
```

---

## 🚀 استخدام أوامر الإدارة

### إرسال التقارير اليومية
```bash
# إرسال تقارير اليوم
python manage.py send_daily_reports

# إرسال تقارير يوم معين
python manage.py send_daily_reports --date 2025-03-25

# وضع الاختبار
python manage.py send_daily_reports --test
```

### إرسال تذكيرات الأقساط
```bash
# فحص وإرسال تذكيرات
python manage.py send_installment_reminders

# عرض فقط بدون إرسال
python manage.py send_installment_reminders --test

# تغيير عدد الأيام
python manage.py send_installment_reminders --days 7
```

---

## ⏰ إعداد Cron Jobs (للتشغيل التلقائي)

### Linux/Mac (crontab)
```bash
# فتح crontab
crontab -e

# إضافة السطور:
# إرسال تقرير يومي الساعة 8 مساءً
0 20 * * * cd /path/to/project && /path/to/venv/bin/python manage.py send_daily_reports

# إرسال تذكيرات الأقساط الساعة 9 صباحاً
0 9 * * * cd /path/to/project && /path/to/venv/bin/python manage.py send_installment_reminders
```

### Windows (Task Scheduler)
1. افتح Task Scheduler
2. Create Basic Task
3. اسم المهمة: "Daily Reports"
4. Trigger: Daily at 8:00 PM
5. Action: Start a program
   - Program: `python`
   - Arguments: `manage.py send_daily_reports`
   - Start in: `G:\accountant\institute_management`

---

## 📋 المميزات المضافة

| الميزة | الوصف |
|--------|-------|
| إشعار الطالب بالإيميل | إيصال دفع مفصل عند التحصيل |
| إشعار الطالب بالواتساب | رسالة نصية بتأكيد الدفع |
| تقرير يومي للمدير | إيميل وواتساب بملخص يومي |
| تقرير إقليمي | ملخص لكل الفروع تحت إدارة المدير الإقليمي |
| تذكيرات الأقساط | إشعار للطالب قبل 3 أيام، يوم، يوم الاستحقاق |
| صفحة بروفايل متكاملة | إحصائيات ورسوم بيانية لكل موظف |

---

## 🔧 التفعيل/التعطيل

في `settings.py`:
```python
ENABLE_EMAIL_NOTIFICATIONS = True  # False للتعطيل
ENABLE_WHATSAPP_NOTIFICATIONS = True  # False للتعطيل
ENABLE_DAILY_REPORTS = True  # False للتعطيل
```
