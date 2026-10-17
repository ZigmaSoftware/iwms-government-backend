"""
Filter backend behind the admin list pages' "Filters" panel.

    filter_backends = [ListParamFilter, filters.SearchFilter, filters.OrderingFilter]

It applies, when present and only for columns the model actually has:

- ``?is_active=true|false`` — the panel's Status filter;
- the flat geo params ``?state_id=`` / ``?district_id=`` / ``?area_type_id=`` /
  ``?corporation_id=`` / ... (comma-separated for several) — the panel's
  Location filter.

Columns the model doesn't carry are ignored, so a page can always send its
whole filter set. Viewsets that already apply the geo params by hand
(``filter_flat_geo_queryset_by_params``) are unaffected: the same filter
applied twice returns the same rows.
"""

from rest_framework.filters import BaseFilterBackend

from app.utils.hierarchy import FLAT_GEO_QUERY_FIELDS

_TRUE = {"true", "1", "yes", "active"}
_FALSE = {"false", "0", "no", "inactive"}


def _column_names(model):
    names = set()
    for field in model._meta.concrete_fields:
        names.add(field.name)
        names.add(field.attname)
    return names


class ListParamFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        params = request.query_params
        columns = _column_names(queryset.model)

        status = str(params.get("is_active", "")).strip().lower()
        if "is_active" in columns and status in _TRUE | _FALSE:
            queryset = queryset.filter(is_active=status in _TRUE)

        for field in FLAT_GEO_QUERY_FIELDS:
            value = params.get(field)
            if not value or field not in columns:
                continue
            values = [item.strip() for item in str(value).split(",") if item.strip()]
            if len(values) == 1:
                queryset = queryset.filter(**{field: values[0]})
            elif values:
                queryset = queryset.filter(**{f"{field}__in": values})
        return queryset
