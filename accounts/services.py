from branches.models import Branch


def get_visible_branches(user):
    """دالة مساعدة لتحديد نطاق رؤية المستخدم"""
    if user.is_superuser or user.is_admin():
        return Branch.objects.filter(is_active=True)
    elif user.user_type == 'regional_manager':
        return user.managed_branches.all()
    else:
        return Branch.objects.filter(id=user.branch_id) if user.branch else Branch.objects.none()
