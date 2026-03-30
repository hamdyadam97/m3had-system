#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نظام الإشعارات - إيميل وواتساب
لإرسال تنبيهات للمديرين والطلاب

الإعدادات:
- المفاتيح الحساسة (Passwords, API Keys): من .env
- الإعدادات العامة (التفعيل، القوالب): من قاعدة البيانات NotificationSettings
"""

import os
import requests
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def get_notification_settings():
    """
    الحصول على إعدادات الإشعارات من قاعدة البيانات
    """
    try:
        from students.notification_models import NotificationSettings
        return NotificationSettings.get_settings()
    except Exception as e:
        logger.error(f"Failed to load notification settings: {e}")
        return None


def get_email_config():
    """
    جلب الإعدادات مع إعطاء الأولوية لملف .env لضمان المصادقة الصحيحة
    """
    db_settings = get_notification_settings()

    config = {
        'enabled': False,
        'host': 'smtp-relay.brevo.com',
        'port': 587,
        'use_tls': True,
        'user': settings.EMAIL_HOST_USER,  # القراءة من settings مباشرة
        'password': settings.EMAIL_HOST_PASSWORD,
        'from_email': settings.DEFAULT_FROM_EMAIL,  # البريد الموثق hamdysarkha@gmail.com
    }

    if db_settings:
        config['enabled'] = db_settings.email_enabled
        # يمكن تحديث السيرفر والمنفذ من قاعدة البيانات إذا لزم الأمر
        config['host'] = db_settings.email_host or config['host']
        config['port'] = db_settings.email_port or config['port']

    return config


def send_email_notification(subject, message, recipient_list, html_message=None):
    config = get_email_config()

    # 1. التأكد من التفعيل (يفضل إجبارها على True للتجربة)
    if not config.get('enabled', True):
        logger.info("Email notifications are disabled in settings")
        return False

    # تنظيف قائمة المستلمين
    recipient_list = [email for email in recipient_list if email]
    if not recipient_list:
        return False

    try:
        from django.core.mail import get_connection

        # 2. المشكلة كانت هنا: يجب التأكد أن البيانات تُقرأ من settings التي بدورها تقرأ من .env
        # قمنا باستخدام الـ Default لضمان عدم وجود قيم فارغة
        connection = get_connection(
            host=config.get('host', 'smtp-relay.brevo.com'),
            port=config.get('port', 587),
            username=settings.EMAIL_HOST_USER,  # القراءة من settings مباشرة أضمن
            password=settings.EMAIL_HOST_PASSWORD,  # المفتاح الذي يبدأ بـ xsmtpsib
            use_tls=config.get('use_tls', True),
        )

        # 3. تحديد البريد المرسل (From Email) بدقة
        # Brevo ترفض الإرسال إذا كان من غير hamdysarkha@gmail.com
        from_email = settings.DEFAULT_FROM_EMAIL

        if html_message:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list,
                connection=connection
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
        else:
            # استخدام send_mail مع التوصيلة (Connection) المفتوحة
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                connection=connection,
                fail_silently=False,
            )

        print(f"✅ Email sent successfully to {recipient_list}")
        return True

    except Exception as e:
        # هنا سيظهر لك السبب الحقيقي للخطأ (مثل خطأ 535 الخاص بالمصادقة)
        logger.error(f"❌ Failed to send email: {str(e)}")
        # طباعة إضافية للدينا في الـ Terminal لتسهيل تتبع الخطأ
        print(f"SMTP Error: {e}")
        return False


def get_whatsapp_config():
    """
    جلب إعدادات الواتساب من .env وقاعدة البيانات
    """
    from django.conf import settings
    db_settings = get_notification_settings()  # تأكد أن هذه الدالة معرفة عندك أيضاً

    # القراءة من settings (المربوطة بملف .env)
    instance_id = getattr(settings, 'WHATSAPP_INSTANCE_ID', '').strip()
    api_token = getattr(settings, 'WHATSAPP_API_TOKEN', '').strip()

    config = {
        'enabled': True,
        'provider': 'ultramsg',
        'api_token': api_token,
        'instance_id': instance_id,
        'api_url': f"https://api.ultramsg.com/{instance_id}/messages/chat" if instance_id else "",
    }

    if db_settings:
        config['enabled'] = db_settings.whatsapp_enabled

    return config


def send_whatsapp_message(phone, message):
    config = get_whatsapp_config()

    if not config['enabled']:
        logger.info("WhatsApp notifications are disabled")
        return False

    # تنظيف وتجهيز الرقم
    clean_phone = str(phone).replace('+', '').replace(' ', '').replace('-', '')
    if clean_phone.startswith('0'):
        clean_phone = '966' + clean_phone[1:]
    elif not clean_phone.startswith('966'):
        clean_phone = '966' + clean_phone

    if not clean_phone.isdigit():
        logger.error(f"Invalid phone number: {phone}")
        return False

    token = config.get('api_token', '').strip()
    instance_id = config.get('instance_id', '').strip()

    if not token or not instance_id:
        logger.error("Missing UltraMsg token or instance_id")
        return False

    # ✅ نفس طريقة الكود التجريبي بالضبط
    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"

    # ✅ بناء payload كـ string (ليس dict) - نفس الطريقة التجريبية
    payload_str = f"token={token}&to={clean_phone}&body={message}&priority=10"

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(
            url,
            data=payload_str,  # ✅ string وليس dict
            headers=headers,
            timeout=15
        )

        print(f"DEBUG URL: {url}")
        print(f"DEBUG Payload: {payload_str}")
        print(f"DEBUG Status: {response.status_code}")
        print(f"DEBUG Response: {response.text}")

        result = response.json()

        if result.get('sent') == 'true':
            logger.info(f"✅ WhatsApp sent to {clean_phone}")
            return True
        else:
            error = result.get('error', response.text)
            logger.error(f"❌ UltraMsg Error: {error}")
            return False

    except Exception as e:
        logger.error(f"❌ WhatsApp Exception: {str(e)}")
        return False

# --- دوال الإشعارات التخصصية (إيصالات، تذكيرات) ---
def send_payment_receipt_to_student(student, income, payment_data):
    """
    إرسال إيصال دفع احترافي للطالب بتصميم عصري
    """
    if not student.email:
        return False

    subject = f'✅ إيصال دفع رقم {payment_data.get("receipt_number", "")}'

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Cairo', Tahoma, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 40px 20px; min-height: 100vh; }}
            .email-wrapper {{ max-width: 650px; margin: 0 auto; }}
            .receipt-container {{ background: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 25px 80px rgba(0,0,0,0.3); }}
            
            /* الهيدر */
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 50px 30px; text-align: center; color: white; position: relative; overflow: hidden; }}
            .header::before {{ content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px); background-size: 20px 20px; opacity: 0.3; }}
            .header-content {{ position: relative; z-index: 1; }}
            .logo {{ font-size: 32px; font-weight: 800; margin-bottom: 10px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
            .receipt-title {{ font-size: 20px; opacity: 0.95; font-weight: 400; margin-bottom: 20px; }}
            .receipt-number {{ background: rgba(255,255,255,0.2); backdrop-filter: blur(10px); padding: 12px 30px; border-radius: 30px; display: inline-block; font-size: 15px; font-weight: 600; border: 1px solid rgba(255,255,255,0.3); }}
            
            /* محتوى الإيصال */
            .content {{ padding: 50px 40px 30px; }}
            .success-badge {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 15px 30px; border-radius: 50px; display: inline-flex; align-items: center; gap: 12px; font-weight: 700; font-size: 16px; margin-bottom: 35px; box-shadow: 0 10px 30px rgba(17,153,142,0.3); }}
            .success-badge::before {{ content: '✓'; width: 28px; height: 28px; background: rgba(255,255,255,0.3); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; }}
            
            .greeting {{ font-size: 20px; color: #2d3748; margin-bottom: 30px; line-height: 1.8; }}
            .greeting strong {{ color: #667eea; font-weight: 700; }}
            
            /* صندوق المبلغ */
            .amount-section {{ background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%); border-radius: 20px; padding: 40px 30px; text-align: center; margin: 30px 0; border: 2px solid #e2e8f0; position: relative; overflow: hidden; }}
            .amount-section::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, #667eea, #764ba2); }}
            .amount-label {{ color: #4a5568; font-size: 16px; margin-bottom: 15px; font-weight: 600; }}
            .amount-value {{ font-size: 56px; font-weight: 800; color: #667eea; line-height: 1; text-shadow: 0 2px 10px rgba(102,126,234,0.2); }}
            .amount-value small {{ font-size: 24px; color: #718096; font-weight: 600; margin-right: 5px; }}
            .amount-currency {{ color: #a0aec0; font-size: 14px; margin-top: 10px; }}
            
            /* تفاصيل الدفع */
            .details-section {{ margin-top: 40px; }}
            .section-title {{ color: #2d3748; font-size: 18px; font-weight: 700; margin-bottom: 25px; padding-right: 15px; border-right: 5px solid #667eea; display: flex; align-items: center; gap: 10px; }}
            .section-title::before {{ content: '📋'; }}
            .details-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
            .detail-item {{ background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 20px; border-radius: 15px; border-right: 4px solid #cbd5e0; transition: transform 0.2s; }}
            .detail-item:hover {{ transform: translateY(-3px); box-shadow: 0 5px 20px rgba(0,0,0,0.1); }}
            .detail-item.full-width {{ grid-column: 1 / -1; }}
            .detail-label {{ color: #718096; font-size: 13px; margin-bottom: 8px; display: block; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
            .detail-value {{ color: #2d3748; font-weight: 700; font-size: 16px; }}
            .detail-value.highlight {{ color: #667eea; font-size: 18px; }}
            .detail-value.danger {{ color: #e53e3e; }}
            
            /* ملخص المدفوعات */
            .summary-section {{ background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%); border: 2px dashed #a0aec0; border-radius: 20px; padding: 30px; margin-top: 35px; position: relative; }}
            .summary-section::before {{ content: '💰'; position: absolute; top: -15px; right: 30px; background: white; padding: 5px 15px; font-size: 20px; border-radius: 20px; }}
            .summary-row {{ display: flex; justify-content: space-between; align-items: center; padding: 15px 0; border-bottom: 1px solid #e2e8f0; }}
            .summary-row:last-child {{ border-bottom: none; font-size: 20px; background: linear-gradient(90deg, #667eea20, #764ba220); margin: 15px -15px -15px; padding: 20px 15px; border-radius: 0 0 17px 17px; }}
            .summary-row:last-child .summary-label {{ font-weight: 700; color: #2d3748; }}
            .summary-row:last-child .summary-value {{ color: #e53e3e; font-weight: 800; font-size: 24px; }}
            .summary-label {{ color: #4a5568; font-weight: 600; }}
            .summary-value {{ color: #2d3748; font-weight: 700; font-size: 18px; }}
            
            /* معلومات الفرع */
            .branch-info {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 35px; margin-top: 40px; border-radius: 20px; text-align: center; position: relative; overflow: hidden; }}
            .branch-info::before {{ content: '🏛️'; font-size: 60px; position: absolute; top: -10px; left: 20px; opacity: 0.1; }}
            .branch-info::after {{ content: '📞'; font-size: 40px; position: absolute; bottom: 10px; right: 30px; opacity: 0.1; }}
            .branch-name {{ font-size: 22px; font-weight: 700; margin-bottom: 15px; position: relative; z-index: 1; }}
            .branch-details {{ font-size: 15px; opacity: 0.95; line-height: 2; position: relative; z-index: 1; }}
            .branch-details strong {{ display: block; margin-bottom: 5px; }}
            
            /* ملاحظات */
            .notes-section {{ margin-top: 30px; padding: 20px; background: #fffbeb; border-right: 4px solid #f59e0b; border-radius: 12px; }}
            .notes-label {{ color: #92400e; font-weight: 700; margin-bottom: 10px; display: block; }}
            .notes-text {{ color: #78350f; line-height: 1.8; }}
            
            /* الفوتر */
            .footer {{ background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%); padding: 40px 30px; text-align: center; color: white; }}
            .footer-content {{ position: relative; z-index: 1; }}
            .footer-logo {{ font-size: 24px; font-weight: 700; margin-bottom: 15px; opacity: 0.9; }}
            .footer-text {{ color: #a0aec0; font-size: 14px; line-height: 2; margin-bottom: 20px; }}
            .footer-divider {{ width: 60px; height: 3px; background: linear-gradient(90deg, #667eea, #764ba2); margin: 20px auto; border-radius: 2px; }}
            .footer-bottom {{ color: #718096; font-size: 12px; margin-top: 20px; }}
            
            @media (max-width: 600px) {{
                body {{ padding: 20px 10px; }}
                .header {{ padding: 35px 20px; }}
                .logo {{ font-size: 24px; }}
                .content {{ padding: 30px 20px; }}
                .details-grid {{ grid-template-columns: 1fr; }}
                .amount-value {{ font-size: 40px; }}
                .summary-row:last-child {{ font-size: 16px; }}
                .summary-row:last-child .summary-value {{ font-size: 20px; }}
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="receipt-container">
                <!-- الهيدر -->
                <div class="header">
                    <div class="header-content">
                        <div class="logo">معهد آفاق التطور</div>
                        <div class="receipt-title">إيصال استلام دفعة إلكتروني</div>
                        <div class="receipt-number">رقم الإيصال: {payment_data.get('receipt_number', '---')}</div>
                    </div>
                </div>
                
                <!-- المحتوى -->
                <div class="content">
                    <div class="success-badge">تم استلام الدفعة بنجاح</div>
                    
                    <p class="greeting">
                        عزيزنا الطالب <strong>{student.full_name}</strong>،<br>
                        نشكركم على دفعتكم. إليكم تفاصيل العملية:
                    </p>
                    
                    <!-- المبلغ -->
                    <div class="amount-section">
                        <div class="amount-label">المبلغ المدفوع</div>
                        <div class="amount-value">
                            {payment_data.get('amount', 0):,.2f}
                            <small>ر.س</small>
                        </div>
                        <div class="amount-currency">ريال سعودي شامل الضريبة</div>
                    </div>
                    
                    <!-- تفاصيل الدفع -->
                    <div class="details-section">
                        <h3 class="section-title">تفاصيل الدفع</h3>
                        <div class="details-grid">
                            <div class="detail-item">
                                <span class="detail-label">تاريخ الدفع</span>
                                <span class="detail-value">{payment_data.get('date', '---')}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">وقت الدفع</span>
                                <span class="detail-value">{payment_data.get('time', '---')}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">طريقة الدفع</span>
                                <span class="detail-value highlight">{payment_data.get('payment_method', '---')}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label">نوع الدفع</span>
                                <span class="detail-value">{payment_data.get('payment_type', '---')}</span>
                            </div>
                            <div class="detail-item full-width">
                                <span class="detail-label">الدورة التدريبية</span>
                                <span class="detail-value highlight">{payment_data.get('course_name', '---')}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- ملخص المدفوعات -->
                    <div class="summary-section">
                        <div class="summary-row">
                            <span class="summary-label">💳 إجمالي الرسوم</span>
                            <span class="summary-value">{payment_data.get('total_price', 0):,.2f} ر.س</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">✓ إجمالي المدفوع</span>
                            <span class="summary-value">{payment_data.get('total_paid', 0):,.2f} ر.س</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">⚠ المبلغ المتبقي</span>
                            <span class="summary-value">{payment_data.get('remaining', 0):,.2f} ر.س</span>
                        </div>
                    </div>
                    
                    <!-- معلومات الفرع -->
                    <div class="branch-info">
                        <div class="branch-name">🏛️ {payment_data.get('branch_name', '---')}</div>
                        <div class="branch-details">
                            <strong>📍 العنوان:</strong> {payment_data.get('branch_address', '---')}<br>
                            <strong>📞 للاستفسار:</strong> {payment_data.get('branch_phone', '---')}
                        </div>
                    </div>
                    
                    <!-- ملاحظات -->
                    {f'''
                    <div class="notes-section">
                        <span class="notes-label">📝 ملاحظات</span>
                        <p class="notes-text">{payment_data.get("notes", "")}</p>
                    </div>
                    ''' if payment_data.get('notes') else ''}
                </div>
                
                <!-- الفوتر -->
                <div class="footer">
                    <div class="footer-content">
                        <div class="footer-logo">معهد آفاق التطور</div>
                        <div class="footer-text">
                            هذا الإيصال تم إنشاؤه آلياً ويُعتمد كإثبات رسمي للدفع<br>
                            يُرجى الاحتفاظ بهذا الإيصال للرجوع إليه عند الحاجة
                        </div>
                        <div class="footer-divider"></div>
                        <div class="footer-bottom">
                            © 2026 معهد آفاق التطور - جميع الحقوق محفوظة
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email_notification(subject, '', [student.email], html_content)


def send_payment_notification_to_manager(manager, income, payment_data, student, collected_by, branch):
    """
    إرسال إشعار دفع للمدير/الأدمن بتصميم احترافي وتفاصيل كاملة
    """
    if not manager.email:
        return False

    # تحديد نوع المدير للإيميل
    if manager.user_type == 'branch_manager':
        role_title = "مدير الفرع"
        role_icon = "🏢"
        role_color = "#667eea"
    elif manager.user_type == 'regional_manager':
        role_title = "المدير الإقليمي"
        role_icon = "🌐"
        role_color = "#9b59b6"
    elif manager.user_type == 'admin':
        role_title = "الإدارة العليا"
        role_icon = "⚡"
        role_color = "#e74c3c"
    else:
        role_title = "مدير"
        role_icon = "👤"
        role_color = "#2d82b7"

    subject = f"{role_icon} إشعار دفع جديد - {branch.name}"

    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: 'Cairo', Tahoma, sans-serif; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); margin: 0; padding: 40px 20px; min-height: 100vh; }}
            .email-wrapper {{ max-width: 700px; margin: 0 auto; }}
            .notification-container {{ background: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }}
            
            /* الهيدر */
            .header {{ background: linear-gradient(135deg, {role_color} 0%, #764ba2 100%); padding: 40px 30px; text-align: center; color: white; position: relative; overflow: hidden; }}
            .header::before {{ content: '{role_icon}'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 150px; opacity: 0.05; }}
            .header-content {{ position: relative; z-index: 1; }}
            .notification-type {{ background: rgba(255,255,255,0.2); backdrop-filter: blur(10px); padding: 8px 25px; border-radius: 30px; font-size: 13px; font-weight: 600; display: inline-block; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.3); }}
            .header-title {{ font-size: 26px; font-weight: 800; margin-bottom: 10px; }}
            .header-subtitle {{ font-size: 16px; opacity: 0.9; }}
            
            /* المحتوى */
            .content {{ padding: 40px; }}
            
            /* صندوق التنبيه */
            .alert-box {{ background: linear-gradient(135deg, {role_color}15 0%, {role_color}05 100%); border-right: 5px solid {role_color}; border-radius: 16px; padding: 25px; margin-bottom: 35px; display: flex; align-items: center; gap: 20px; }}
            .alert-icon {{ width: 60px; height: 60px; background: linear-gradient(135deg, {role_color} 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; flex-shrink: 0; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
            .alert-content {{ flex: 1; }}
            .alert-title {{ font-size: 18px; font-weight: 700; color: #2d3748; margin-bottom: 8px; }}
            .alert-text {{ color: #4a5568; font-size: 15px; line-height: 1.6; }}
            
            /* صندوق المبلغ */
            .amount-highlight {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 30px; text-align: center; color: white; margin: 30px 0; box-shadow: 0 15px 40px rgba(102,126,234,0.3); position: relative; overflow: hidden; }}
            .amount-highlight::before {{ content: '💰'; position: absolute; top: -20px; right: -20px; font-size: 100px; opacity: 0.1; }}
            .amount-highlight-label {{ font-size: 14px; opacity: 0.9; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; }}
            .amount-highlight-value {{ font-size: 48px; font-weight: 800; text-shadow: 0 2px 10px rgba(0,0,0,0.2); }}
            .amount-highlight-currency {{ font-size: 20px; opacity: 0.9; margin-top: 5px; }}
            
            /* تفاصيل العملية */
            .section {{ margin-bottom: 35px; }}
            .section-title {{ font-size: 18px; font-weight: 700; color: #2d3748; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; padding-right: 15px; border-right: 4px solid {role_color}; }}
            .details-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
            .detail-card {{ background: #f8fafc; border-radius: 16px; padding: 20px; border: 1px solid #e2e8f0; transition: all 0.3s; }}
            .detail-card:hover {{ transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.1); border-color: {role_color}; }}
            .detail-card.full-width {{ grid-column: 1 / -1; }}
            .detail-card-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
            .detail-icon {{ width: 40px; height: 40px; background: linear-gradient(135deg, {role_color}20 0%, {role_color}10 100%); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
            .detail-card-label {{ color: #718096; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
            .detail-card-value {{ color: #2d3748; font-weight: 700; font-size: 16px; }}
            .detail-card-value.highlight {{ color: {role_color}; font-size: 18px; }}
            .detail-card-value.large {{ font-size: 20px; }}
            
            /* معلومات إضافية */
            .info-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 25px; }}
            .info-item {{ background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%); padding: 20px 15px; border-radius: 16px; text-align: center; border: 2px solid transparent; transition: all 0.3s; }}
            .info-item:hover {{ border-color: {role_color}; transform: translateY(-3px); }}
            .info-icon {{ font-size: 28px; margin-bottom: 10px; }}
            .info-label {{ color: #718096; font-size: 12px; margin-bottom: 5px; font-weight: 600; }}
            .info-value {{ color: #2d3748; font-weight: 700; font-size: 16px; }}
            
            /* الفوتر */
            .footer {{ background: #1a202c; padding: 30px; text-align: center; color: #a0aec0; }}
            .footer-text {{ font-size: 13px; line-height: 1.8; }}
            .footer-highlight {{ color: {role_color}; font-weight: 700; }}
            
            @media (max-width: 600px) {{
                body {{ padding: 20px 10px; }}
                .content {{ padding: 25px 20px; }}
                .details-grid {{ grid-template-columns: 1fr; }}
                .info-grid {{ grid-template-columns: 1fr; }}
                .amount-highlight-value {{ font-size: 36px; }}
                .alert-box {{ flex-direction: column; text-align: center; }}
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="notification-container">
                <!-- الهيدر -->
                <div class="header">
                    <div class="header-content">
                        <div class="notification-type">{role_title}</div>
                        <div class="header-title">إشعار تحصيل مالي جديد</div>
                        <div class="header-subtitle">تم تسجيل عملية دفع في النظام</div>
                    </div>
                </div>
                
                <!-- المحتوى -->
                <div class="content">
                    <!-- تنبيه -->
                    <div class="alert-box">
                        <div class="alert-icon">🔔</div>
                        <div class="alert-content">
                            <div class="alert-title">تنبيه: دفعة جديدة مسجلة</div>
                            <div class="alert-text">
                                تم تسجيل عملية دفع جديدة بواسطة <strong>{payment_data.get('collector_name', '---')}</strong> 
                                في فرع <strong>{branch.name}</strong> بتاريخ {payment_data.get('date', '---')}
                            </div>
                        </div>
                    </div>
                    
                    <!-- المبلغ -->
                    <div class="amount-highlight">
                        <div class="amount-highlight-label">المبلغ المحصل</div>
                        <div class="amount-highlight-value">{payment_data.get('amount', 0):,.2f}</div>
                        <div class="amount-highlight-currency">ريال سعودي</div>
                    </div>
                    
                    <!-- تفاصيل الطالب -->
                    <div class="section">
                        <h3 class="section-title">👤 معلومات الطالب</h3>
                        <div class="details-grid">
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">👤</div>
                                    <span class="detail-card-label">اسم الطالب</span>
                                </div>
                                <div class="detail-card-value large">{student.full_name}</div>
                            </div>
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">📱</div>
                                    <span class="detail-card-label">رقم الهاتف</span>
                                </div>
                                <div class="detail-card-value">{student.phone or 'غير متوفر'}</div>
                            </div>
                            <div class="detail-card full-width">
                                <div class="detail-card-header">
                                    <div class="detail-icon">📚</div>
                                    <span class="detail-card-label">الدورة المسجل بها</span>
                                </div>
                                <div class="detail-card-value highlight">{payment_data.get('course_name', '---')}</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- تفاصيل الدفع -->
                    <div class="section">
                        <h3 class="section-title">💳 تفاصيل العملية المالية</h3>
                        <div class="details-grid">
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">🧾</div>
                                    <span class="detail-card-label">رقم الإيصال</span>
                                </div>
                                <div class="detail-card-value highlight">{payment_data.get('receipt_number', '---')}</div>
                            </div>
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">💳</div>
                                    <span class="detail-card-label">طريقة الدفع</span>
                                </div>
                                <div class="detail-card-value highlight">{payment_data.get('payment_method', '---')}</div>
                            </div>
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">📋</div>
                                    <span class="detail-card-label">نوع الدفع</span>
                                </div>
                                <div class="detail-card-value">{payment_data.get('payment_type', '---')}</div>
                            </div>
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">📅</div>
                                    <span class="detail-card-label">تاريخ ووقت العملية</span>
                                </div>
                                <div class="detail-card-value">{payment_data.get('date', '---')} - {payment_data.get('time', '---')}</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- ملخص مالي -->
                    <div class="section">
                        <h3 class="section-title">📊 ملخص الحساب المالي</h3>
                        <div class="info-grid">
                            <div class="info-item">
                                <div class="info-icon">💰</div>
                                <div class="info-label">إجمالي الرسوم</div>
                                <div class="info-value">{payment_data.get('total_price', 0):,.2f} ر.س</div>
                            </div>
                            <div class="info-item">
                                <div class="info-icon">✅</div>
                                <div class="info-label">إجمالي المدفوع</div>
                                <div class="info-value">{payment_data.get('total_paid', 0):,.2f} ر.س</div>
                            </div>
                            <div class="info-item">
                                <div class="info-icon">⚠️</div>
                                <div class="info-label">المبلغ المتبقي</div>
                                <div class="info-value" style="color: #e53e3e;">{payment_data.get('remaining', 0):,.2f} ر.س</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- معلومات الفرع والموظف -->
                    <div class="section">
                        <h3 class="section-title">🏢 معلومات إضافية</h3>
                        <div class="details-grid">
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">🏛️</div>
                                    <span class="detail-card-label">الفرع</span>
                                </div>
                                <div class="detail-card-value">{branch.name}</div>
                                <div style="color: #718096; font-size: 13px; margin-top: 5px;">{payment_data.get('branch_address', '')}</div>
                            </div>
                            <div class="detail-card">
                                <div class="detail-card-header">
                                    <div class="detail-icon">👨‍💼</div>
                                    <span class="detail-card-label">أُضيفت بواسطة</span>
                                </div>
                                <div class="detail-card-value">{payment_data.get('collector_name', '---')}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- الفوتر -->
                <div class="footer">
                    <p class="footer-text">
                        هذا الإشعار تم إرساله تلقائياً من نظام إدارة المعهد<br>
                        <span class="footer-highlight">معهد آفاق التطور</span> - نظام إدارة متكامل
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email_notification(subject, '', [manager.email], html_content)


def send_whatsapp_payment_notification(phone, income, student, branch, collected_by, recipient_type):
    """
    إرسال إشعار دفع عبر واتساب
    """
    if not phone:
        return False

    messages = {
        'student': f"""✅ *تم استلام دفعة جديدة*

*الطالب:* {student.full_name}
*الدورة:* {income.course.name if income.course else 'غير محدد'}
*المبلغ:* {income.amount:,.2f} ر.س
*نوع الدفع:* {income.get_income_type_display()}
*التاريخ:* {income.date}

📊 *ملخص الحساب:*
• إجمالي المبلغ: {student.total_price:,.2f} ر.س
• إجمالي المدفوع: {student.get_total_paid():,.2f} ر.س
• المتبقي: {student.get_remaining_amount():,.2f} ر.س

شكراً لاختياركم معاهدنا التعليمية 🎓""",

        'manager': f"""🔔 *تنبيه: دفعة جديدة*

*الفرع:* {branch.name}
*الموظف:* {collected_by.get_full_name() if collected_by else 'غير معروف'}

*الطالب:* {student.full_name}
*المبلغ:* {income.amount:,.2f} ر.س
*نوع الدفع:* {income.get_income_type_display()}
*الوقت:* {timezone.now().strftime('%H:%M')}

أنت تستلم هذا الإشعار كمدير للفرع 📍""",

        'regional': f"""📊 *تنبيه إقليمي*

*الفرع:* {branch.name}
*الطالب:* {student.full_name}
*المبلغ:* {income.amount:,.2f} ر.س
*نوع الدفع:* {income.get_income_type_display()}

أنت تستلم هذا الإشعار كمدير إقليمي 🌐""",

        'admin': f"""🔔 *تنبيه نظام - للإدارة*

*الفرع:* {branch.name}
*الموظف:* {collected_by.get_full_name() if collected_by else 'غير معروف'}
*الطالب:* {student.full_name}
*المبلغ:* {income.amount:,.2f} ر.س
*نوع الدفع:* {income.get_income_type_display()}

هذا الإشعار موجه للإدارة العليا ⚠️"""
    }

    message = messages.get(recipient_type, messages['admin'])
    return send_whatsapp_message(phone, message)


def create_in_app_notification(recipient, title, message, notification_type, **kwargs):
    """
    إنشاء إشعار داخلي في النظام
    """
    from .models import Notification
    try:
        notification = Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            **kwargs
        )
        return notification
    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
        return None


def notify_on_payment(income):
    """
    الدالة المركزية التي تستدعيها عند حفظ أي عملية دفع
    """
    from accounts.models import User
    from django.db import models

    branch = income.branch
    student = income.student
    collected_by = income.collected_by

    # بيانات الدفع الكاملة
    payment_data = {
        'receipt_number': f"REC-{income.id:06d}",
        'course_name': income.course.name if income.course else 'غير محدد',
        'branch_name': branch.name if branch else 'غير محدد',
        'branch_phone': branch.phone if branch else 'غير محدد',
        'branch_address': branch.address if branch else 'غير محدد',
        'amount': float(income.amount),
        'total_price': float(student.total_price) if student.total_price else 0,
        'total_paid': float(student.get_total_paid()) if hasattr(student, 'get_total_paid') else float(income.amount),
        'remaining': float(student.get_remaining_amount()) if hasattr(student, 'get_remaining_amount') else 0,
        'date': income.date.strftime('%Y-%m-%d'),
        'time': income.created_at.strftime('%H:%M') if hasattr(income, 'created_at') else '',
        'payment_method': income.get_payment_method_display() if hasattr(income, 'get_payment_method_display') else 'نقدي',
        'payment_type': income.get_income_type_display() if hasattr(income, 'get_income_type_display') else 'دفعة',
        'collector_name': collected_by.get_full_name() if collected_by else 'النظام',
        'notes': income.notes if hasattr(income, 'notes') and income.notes else '',
    }

    # إرسال للطالب (بشكل غير متزامن باستخدام Celery لو متاح)
    if student.email:
        # استخدام Celery للإرسال غير المتزامن لو متاح
        try:
            from students.tasks import send_payment_receipt_task
            send_payment_receipt_task.delay(student.id, income.id, payment_data)
        except Exception:
            # لو Celery مش شغال، ابعت مباشرة
            send_payment_receipt_to_student(student, income, payment_data)
    
    if student.phone:
        send_whatsapp_payment_notification(student.phone, income, student, branch, collected_by, 'student')

    # إرسال للمديرين (فرع، إقليمي، أدمن)
    target_users = User.objects.filter(is_active=True).filter(
        models.Q(branch=branch, user_type='branch_manager') |
        models.Q(user_type='admin') |
        models.Q(is_superuser=True)
    ).distinct()

    for user in target_users:
        if user.email:
            send_payment_notification_to_manager(user, income, payment_data, student, collected_by, branch)
        create_in_app_notification(user, "دفعة جديدة", f"{student.full_name}: {income.amount}", 'income',
                                   related_income=income)


def notify_managers_on_payment(income):
    """
    دالة توافقية - تستدعي الدالة الجديدة
    """
    notify_on_payment(income)
