from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.models.screen_managements.userscreen import UserScreen
from app.serializers.screen_managements.userscreen_serializer import UserScreenSerializer


class UserScreenViewSet(viewsets.ModelViewSet):
    serializer_class = UserScreenSerializer
    queryset = UserScreen.objects.filter(is_deleted=False)
    lookup_field = "unique_id"

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)

        # Ensure backend-only fields don't fail "required" validation when UI omits them.
        if not data.get("icon_name"):
            data["icon_name"] = (data.get("userscreen_name") or "").strip()

        if not data.get("order_no"):
            mainscreen_id = data.get("mainscreen_id")
            if mainscreen_id:
                with transaction.atomic():
                    last = (
                        UserScreen.objects.select_for_update()
                        .filter(mainscreen_id=mainscreen_id, is_deleted=False)
                        .order_by("-order_no")
                        .first()
                    )
                    data["order_no"] = (last.order_no if last else 0) + 1

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter: ?mainscreen_id=MAINSCREEN-0001
        mainscreen_param = self.request.query_params.get("mainscreen_id")
        if mainscreen_param:
            queryset = queryset.filter(mainscreen_id=mainscreen_param)

        # Filter: ?userscreen_name=xxx
        name_param = self.request.query_params.get("userscreen_name")
        if name_param:
            queryset = queryset.filter(userscreen_name__icontains=name_param)

        # Filter: ?folder_name=xxx
        folder_param = self.request.query_params.get("folder_name")
        if folder_param:
            queryset = queryset.filter(folder_name__icontains=folder_param)

        return queryset.order_by("order_no")

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_value = self.kwargs.get(lookup_field)

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
            {"message": "User Screen deleted successfully"},
            status=status.HTTP_200_OK
        )
