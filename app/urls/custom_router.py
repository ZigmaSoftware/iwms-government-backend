from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.urls import path
from collections import OrderedDict

from ..utils.swagger import register_group_basename


class GroupedRouter(DefaultRouter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_map = OrderedDict()

    def register_group(
        self,
        group,
        prefix,
        viewset,
        basename=None,
        include_group_in_prefix=True,
    ):
        """
        group    → masters / assets / customers
        prefix   → continents / fuels
        URL OUT  → /masters/continents/
        """

        if group not in self.group_map:
            self.group_map[group] = []

        base = basename or f"{group}-{prefix}".replace("/", "-")
        if include_group_in_prefix:
            full_prefix = f"{group}/{prefix}"
        else:
            full_prefix = prefix

        register_group_basename(base, group, prefix, include_group_in_prefix)

        self.group_map[group].append({
            "prefix": prefix,
            "full_prefix": full_prefix,
            "basename": base,
            "viewset": viewset
        })

        #  REGISTER WITH GROUP PREFIX
        return super().register(full_prefix, viewset, basename=base)

    def get_api_root_view(self, api_urls=None):
        grouped = self.group_map

        class GroupedAPIRoot(APIView):
            _ignore_model_permissions = True

            def get(self, request, *args, **kwargs):
                data = OrderedDict()

                for group_name, items in grouped.items():
                    data[group_name] = OrderedDict()

                    for entry in items:
                        url_name = f"{entry['basename']}-list"
                        try:
                            url = reverse(url_name, request=request)
                        except Exception:
                            url = None

                        label = entry['prefix'].replace("-", " ").title()
                        data[group_name][label] = url

                return Response(data)

        return GroupedAPIRoot.as_view()

    def get_urls(self):
        urls = super().get_urls()

        # Root endpoint
        root = [path("", self.get_api_root_view(), name="grouped-api-root")]

        return root + urls
