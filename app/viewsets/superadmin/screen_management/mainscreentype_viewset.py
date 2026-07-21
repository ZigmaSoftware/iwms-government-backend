from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.serializers.superadmin.screen_management.mainscreentype_serializer import (
    MainScreenTypeSerializer
)


class MainScreenTypeViewSet(viewsets.ModelViewSet):
    serializer_class = MainScreenTypeSerializer
    queryset = MainScreenType.objects.filter(is_deleted=False)
    lookup_field = "unique_id"

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

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_deleted = True
        instance.save(update_fields=["is_active", "is_deleted"])

        return Response(
            {"message": "Main Screen Type deleted successfully"},
            status=status.HTTP_200_OK
        )
