"""
A DRF mixin that makes corporation / hierarchy scoping the *default* for a
ModelViewSet instead of something each viewset must remember to opt into.

Historically every viewset called `filter_flat_geo_queryset_by_requester_scope`
by hand in its own `get_queryset`, so a forgotten call silently leaked another
corporation's rows (gaps G1/G2/G5). Inheriting from `FlatGeoScopedViewSetMixin`
applies both the explicit hierarchy query params and the requester's own
`StaffDataScope` cap automatically; a genuinely global master opts out with
``flat_geo_scope_enabled = False``.
"""

from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)


class FlatGeoScopedViewSetMixin:
    """Mixin for viewsets whose model carries the flat geo FK block
    (state/district/area_type/corporation/.../panchayat), directly or via a
    relation prefix.

    In ``get_queryset`` it applies, on top of ``super().get_queryset()``:

    1. explicit ``?corporation_id=`` / ``?district_id=`` / ... query params, and
    2. the requester's own ``StaffDataScope`` cap (inclusive-downward), denying
       a non-super staff user with no scope row by default (G4).

    Config knobs (class attributes):

    - ``flat_geo_scope_enabled`` — set ``False`` to opt a truly global master out.
    - ``flat_geo_param_prefix`` — related-path prefix for the param filter,
      e.g. ``"trip_assignment_id__"``.
    - ``flat_geo_field_map`` — ``{scope_field: queryset_field}`` for models that
      reach their geo columns through a relation.
    """

    flat_geo_scope_enabled = True
    flat_geo_param_prefix = ""
    flat_geo_field_map = None

    def get_queryset(self):
        queryset = super().get_queryset()
        if not getattr(self, "flat_geo_scope_enabled", True):
            return queryset

        request = getattr(self, "request", None)
        if request is None:
            return queryset

        queryset = filter_flat_geo_queryset_by_params(
            queryset,
            request.query_params,
            prefix=self.flat_geo_param_prefix,
        )
        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset,
            request.user,
            field_map=self.flat_geo_field_map,
        )
        return queryset
