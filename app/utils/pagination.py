import math
from collections import OrderedDict

from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from drf_yasg import openapi


class LimitOffsetWithPage(LimitOffsetPagination):
    """
    Limit/offset pagination that also exposes page metadata.
    """

    def paginate_queryset(self, queryset, request, view=None):
        """
        Accept either standard limit/offset or a friendlier page param.
        If ?page is provided (1-based) and ?offset is not, convert it to offset.
        """
        page_param = request.query_params.get("page")
        offset_param = request.query_params.get(self.offset_query_param)

        if page_param is not None and offset_param is None:
            try:
                page = max(int(page_param), 1)
            except (TypeError, ValueError):
                page = 1
            limit = self.get_limit(request) or self.default_limit
            computed_offset = (page - 1) * (limit or 0)
            # Inject computed offset into the request query params copy used by DRF
            request._request.GET = request._request.GET.copy()
            request._request.GET[self.offset_query_param] = str(computed_offset)

        return super().paginate_queryset(queryset, request, view)

    def get_schema_operation_parameters(self, view):
        params = super().get_schema_operation_parameters(view) or []
        page_param = {
            "name": "page",
            "in": openapi.IN_QUERY,
            "description": "One-based page number (falls back to limit/offset if provided).",
            "required": False,
            "schema": {
                "type": openapi.TYPE_INTEGER,
            },
        }
        return list(params) + [page_param]

    def get_paginated_response_schema(self, schema):
        paginator_schema = super().get_paginated_response_schema(schema)
        properties = paginator_schema.setdefault("properties", {})
        properties.setdefault("page", {
            "type": "integer",
            "example": 1,
            "description": "Current page number derived from offset and limit.",
        })
        properties.setdefault("total_pages", {
            "type": "integer",
            "example": 1,
            "description": "Total number of pages available.",
        })

        required = list(paginator_schema.get("required", []))
        for field in ("page", "total_pages"):
            if field not in required:
                required.append(field)
        paginator_schema["required"] = required
        return paginator_schema

    def get_paginated_response(self, data):
        limit = self.limit or self.count or 1
        current_page = (self.offset // limit) + 1
        total_pages = math.ceil(self.count / limit) if self.count else 1

        return Response(
            OrderedDict(
                [
                    ("count", self.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page", current_page),
                ("total_pages", total_pages),
                    ("results", data),
                ]
            )
        )
