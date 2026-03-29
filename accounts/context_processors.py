"""
Context Processors للإشعارات
"""


def notifications_context(request):
    """
    إضافة الإشعارات الغير مقروءة لـ context في كل الصفحات
    """
    context = {
        'unread_notifications': [],
        'unread_notifications_count': 0,
    }
    
    if request.user.is_authenticated:
        # جلب آخر 10 إشعارات غير مقروءة
        unread_notifications = request.user.notifications.filter(
            is_read=False
        ).select_related('related_income', 'related_student')[:10]
        
        context['unread_notifications'] = unread_notifications
        context['unread_notifications_count'] = unread_notifications.count()
    
    return context
