from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.staff_access_configuration_serializer import (
    StaffAccessConfigurationSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class StaffAccessConfigurationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Staffcreation.objects.select_related(
        "personal_details",
        "department_id",
        "designation_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    ).all()
    serializer_class = StaffAccessConfigurationSerializer
    lookup_field = "staff_unique_id"
    permission_resource = "StaffAccessConfiguration"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staff-access-configuration"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=None,
            new_data=self._serialize_instance(staff),
        )
        return Response(
            serializer.to_representation(result),
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        try:
            result = serializer.save()
        except IntegrityError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff = result["staff"]
        self.log_audit(
            request,
            instance=staff,
            previous_data=previous_data,
            new_data=self._serialize_instance(staff),
        )
        return Response(serializer.to_representation(result))

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
            transaction.set_rollback(True)

        return Response(
            {
                "valid": True,
                "summary": {
                    "basicInfo": serializer.validated_data.get("basicInfo", {}),
                    "loginConfig": {
                        key: value
                        for key, value in serializer.validated_data.get("loginConfig", {}).items()
                        if key != "password"
                    },
                    "permissions": len(serializer.validated_data.get("permissions") or []),
                    "dashboardPermissions": len(
                        serializer.validated_data.get("dashboardPermissions") or []
                    ),
                    "dataScope": bool(result.get("data_scope")),
                },
            },
            status=status.HTTP_200_OK,
        )
