def notifications_context(request):
    """
    إضافة الإشعارات الغير مقروءة لـ context في كل الصفحات
    (معطلة - تم إزالة نظام الإشعارات)
    """
    return {
        'unread_notifications': [],
        'unread_notifications_count': 0,
    }
