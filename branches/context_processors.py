# branches/context_processors.
from .models import Branch

from .models import Branch


def branch_context(request):
    if request.user.is_authenticated:
        user = request.user
        branches = []

        # 1. لو أدمن أو سوبر يوزر -> يشوف كل الفروع
        if user.is_superuser or user.user_type == 'admin':
            branches = Branch.objects.filter(is_active=True)

        # 2. لو مدير إقليمي -> يشوف فروعه المحددة في الـ ManyToMany
        elif user.user_type == 'regional_manager':
            branches = user.managed_branches.all()

        # 3. أي رتبة تانية (موظف/مدير فرع) -> يشوف فرعه هو بس
        else:
            if user.branch:
                branches = Branch.objects.filter(id=user.branch.id)

        return {
            'branches': branches,
            # التعديل هنا: لو هو أدمن خليه دايماً True عشان تظهر "تبديل الفرع"
            'is_global_view': user.is_superuser or user.user_type == 'admin' or (
                        hasattr(branches, 'count') and branches.count() > 1)
        }
    return {'branches': [], 'is_global_view': False}