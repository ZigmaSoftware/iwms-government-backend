from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.models.screen_managements.userscreenaction import UserScreenAction
from app.serializers.screen_managements.userscreenaction_serializer import (
    UserScreenActionSerializer
)


class UserScreenActionViewSet(viewsets.ModelViewSet):
    serializer_class = UserScreenActionSerializer
    queryset = UserScreenAction.objects.filter(is_deleted=False)
    lookup_field = "unique_id"

    def get_queryset(self):
        queryset = super().get_queryset()

        # ?action_name=xxx
        action_param = self.request.query_params.get("action_name")
        if action_param:
            queryset = queryset.filter(action_name__icontains=action_param)

        # ?variable_name=xxx
        variable_param = self.request.query_params.get("variable_name")
        if variable_param:
            queryset = queryset.filter(variable_name__icontains=variable_param)

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
            {"message": "User Screen Action deleted successfully"},
            status=status.HTTP_200_OK
        )
