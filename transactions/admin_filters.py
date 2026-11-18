from datetime import date

from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class DateRangeFilter(admin.FieldListFilter):
    """فلتر بفترة (من / إلى) على حقل تاريخ أو تاريخ ووقت."""

    template = 'admin/date_range_filter.html'

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.param_gte = f'{field_path}__date__gte'
        self.param_lte = f'{field_path}__date__lte'
        super().__init__(field, request, params, model, model_admin, field_path)
        self.title = field.verbose_name

    def expected_parameters(self):
        return [self.param_gte, self.param_lte]

    def has_output(self):
        return True

    def _value(self, param):
        value = self.used_parameters.get(param)
        if isinstance(value, (list, tuple)):
            value = value[-1] if value else None
        if not value:
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    def queryset(self, request, queryset):
        gte = self._value(self.param_gte)
        lte = self._value(self.param_lte)
        if gte:
            queryset = queryset.filter(**{self.param_gte: gte})
        if lte:
            queryset = queryset.filter(**{self.param_lte: lte})
        return queryset

    def choices(self, changelist):
        gte = self._value(self.param_gte)
        lte = self._value(self.param_lte)
        hidden = []
        for key, values in changelist.params.items():
            if key in (self.param_gte, self.param_lte, 'p'):
                continue
            if not isinstance(values, (list, tuple)):
                values = [values]
            for v in values:
                hidden.append((key, v))
        yield {
            'selected': bool(gte or lte),
            'param_gte': self.param_gte,
            'param_lte': self.param_lte,
            'value_gte': gte.isoformat() if gte else '',
            'value_lte': lte.isoformat() if lte else '',
            'hidden': hidden,
            'reset_url': changelist.get_query_string(remove=[self.param_gte, self.param_lte]),
            'display': _('All'),
        }
