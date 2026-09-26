"""SearchFilter that can search through plain unique_id reference columns.

Models no longer carry ForeignKeys, so a search field like
``property_id__property_name`` has no join to follow. Declare such fields as
``"<column>=<Model path>.<field>"`` instead, e.g.::

    search_fields = [
        "sub_property_name",
        "property_id=app.models.masters.waste_masters.property.Property.property_name",
    ]

Each term then matches rows whose ``property_id`` is the unique_id of a
Property whose ``property_name`` contains the term (one subquery, no join).
References can be chained, each hop a plain id column on the previous
model, e.g. assignment -> staff template -> driver name::

    "staff_template_id=app...StaffTemplate.driver_id=app...Staff.employee_name"

Ordinary search fields behave exactly as in DRF's SearchFilter.
"""

import importlib
import operator
from functools import reduce

from django.db.models import Q
from rest_framework import filters


def _resolve(path):
    model_path, field = path.rsplit(".", 1)
    module_path, class_name = model_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name), field


class PlainRefSearchFilter(filters.SearchFilter):
    def filter_queryset(self, request, queryset, view):
        search_fields = self.get_search_fields(view, request)
        search_terms = self.get_search_terms(request)
        if not search_fields or not search_terms:
            return queryset

        plain = [f for f in search_fields if "=" not in f]
        refs = [f.split("=") for f in search_fields if "=" in f]
        orm_lookups = [self.construct_search(str(f), queryset) for f in plain]

        for term in search_terms:
            clauses = [Q(**{lookup: term}) for lookup in orm_lookups]
            for column, *hops in refs:
                clauses.append(Q(**{f"{column}__in": self._chain(hops, term)}))
            queryset = queryset.filter(reduce(operator.or_, clauses))
        return queryset

    @staticmethod
    def _chain(hops, term):
        """Innermost hop matches the term; each outer hop keeps rows whose
        plain id column points into the inner result."""
        model, field = _resolve(hops[-1])
        inner = model.objects.filter(**{f"{field}__icontains": term}).values("pk")
        for hop in reversed(hops[:-1]):
            model, column = _resolve(hop)
            inner = model.objects.filter(**{f"{column}__in": inner}).values("pk")
        return inner
