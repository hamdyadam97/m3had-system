from django import template

register = template.Library()


@register.filter
def div(value, arg):
    """قسمة رقم على رقم آخر"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0
