# branches/context_processors.
from .models import Branch


def branch_context(request):
    if request.user.is_authenticated:
        user = request.user
        if user.is_superuser or user.user_type == 'admin':
            branches = Branch.objects.filter(is_active=True)
        elif user.user_type == 'regional_manager':
            branches = user.managed_branches.all()
        else:
            branches = Branch.objects.filter(id=user.branch_id) if user.branch else []

        return {
            'branches': branches,
            'is_global_view': branches.count() > 1 if hasattr(branches, 'count') else False
        }
    return {}