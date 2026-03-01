#!/usr/bin/env python
"""
سكربت إعداد المشروع
"""

import os
import sys
import subprocess


def run_command(command, description):
    """تشغيل أمر وعرض النتيجة"""
    print(f"\n📌 {description}...")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ تم بنجاح!")
        return True
    else:
        print(f"❌ فشل: {result.stderr}")
        return False


def main():
    print("=" * 60)
    print("    إعداد نظام إدارة المعاهد")
    print("=" * 60)
    
    # التحقق من Python
    print(f"\n🐍 Python: {sys.version}")
    
    # تثبيت المتطلبات
    if not run_command("pip install -r requirements.txt", "تثبيت المتطلبات"):
        return
    
    # إنشاء migrations
    if not run_command("python manage.py makemigrations", "إنشاء migrations"):
        return
    
    # تطبيق migrations
    if not run_command("python manage.py migrate", "تطبيق migrations"):
        return
    
    # إنشاء البيانات التجريبية
    response = input("\n🤔 هل تريد إنشاء بيانات تجريبية؟ (y/n): ")
    if response.lower() == 'y':
        run_command("python create_demo_data.py", "إنشاء البيانات التجريبية")
    
    print("\n" + "=" * 60)
    print("✅ تم إعداد المشروع بنجاح!")
    print("=" * 60)
    print("\nلتشغيل الخادم:")
    print("  ➜ python manage.py runserver")
    print("\nأو استخدم:")
    print("  ➜ bash run.sh")
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
