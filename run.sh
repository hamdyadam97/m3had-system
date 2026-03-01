#!/bin/bash

echo "=========================================="
echo "    نظام إدارة المعاهد - تشغيل الخادم    "
echo "=========================================="
echo ""

# التحقق من وجود Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت"
    exit 1
fi

# تثبيت المتطلبات إذا لزم الأمر
echo "📦 التحقق من المتطلبات..."
pip install -q -r requirements.txt

# تشغيل الخادم
echo "🚀 تشغيل الخادم..."
echo ""
echo "الرجاء فتح المتصفح على العنوان:"
echo "  ➜ http://127.0.0.1:8000/"
echo ""
echo "بيانات تسجيل الدخول الافتراضية:"
echo "  ➜ اسم المستخدم: admin"
echo "  ➜ كلمة المرور: admin123"
echo ""
echo "=========================================="
echo ""

python manage.py runserver
