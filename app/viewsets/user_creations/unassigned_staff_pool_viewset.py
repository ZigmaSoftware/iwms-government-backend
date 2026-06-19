from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from app.models.user_creations.unassigned_staff_pool import UnassignedStaffPool
from app.serializers.user_creations.unassigned_staff_pool_serializer import (
    UnassignedStaffPoolSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin


class UnassignedStaffPoolViewSet(ModelViewSet,AuditViewSetMixin):
    """
    Controls staff availability.
    Used by system + supervisors.
    """

    serializer_class = UnassignedStaffPoolSerializer
    permission_resource = "UnassignedStaffPool"
    swagger_tags = ["Desktop / Staff Availability"]

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "unassigned-staff-pool"

    def get_queryset(self):
        qs = UnassignedStaffPool.objects.all()
        status_param = self.request.query_params.get("status")
        if status_param:
            return qs.filter(status=status_param)
        return qs.filter(status=UnassignedStaffPool.Status.AVAILABLE)

    def perform_create(self, serializer):
        self._validate_daily_trip_assignment_alignment(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_daily_trip_assignment_alignment(serializer.validated_data)
        serializer.save()

    def _validate_daily_trip_assignment_alignment(self, attrs):
        return None

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion is not allowed. Update status instead."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
