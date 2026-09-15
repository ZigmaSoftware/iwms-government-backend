from django.shortcuts import get_object_or_404
from rest_framework import filters, viewsets, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.serializers.superadmin.screen_management.mainscreentype_serializer import (
    MainScreenTypeSerializer
)
from app.utils.pagination import LimitOffsetWithPage

MAIN_SCREEN_TYPE_CACHE_SCOPES = ("main_screen_type_list", "main_screen_type_detail")


class MainScreenTypeViewSet(viewsets.ModelViewSet):
    throttle_scope = "main_screen_type"
    serializer_class = MainScreenTypeSerializer
    queryset = MainScreenType.objects.filter(is_deleted=False)
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["type_name"]
    ordering_fields = ["type_name", "is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()

        # Optional filter: ?type_name=xxx
        type_param = self.request.query_params.get("type_name")
        if type_param:
            queryset = queryset.filter(type_name__icontains=type_param)

        return queryset

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)

        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    @cache_api("main_screen_type_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("main_screen_type_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save()
        invalidate_on_commit(*MAIN_SCREEN_TYPE_CACHE_SCOPES)

    def perform_update(self, serializer):
        serializer.save()
        invalidate_on_commit(*MAIN_SCREEN_TYPE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_deleted = True
        instance.save(update_fields=["is_active", "is_deleted"])

        invalidate_on_commit(*MAIN_SCREEN_TYPE_CACHE_SCOPES)
        return Response(
            {"message": "Main Screen Type deleted successfully"},
            status=status.HTTP_200_OK
        )
