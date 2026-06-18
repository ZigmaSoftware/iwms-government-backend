from django.shortcuts import get_object_or_404

from rest_framework.response import Response
from rest_framework import viewsets
from app.models.role_assigns.staffUserType import StaffUserType
from app.serializers.role_assigns.staffusertype_serializer import StaffUserTypeSerializer
from rest_framework.decorators import action
from app.utils.audit_mixin import AuditViewSetMixin


class StaffUserTypeViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
    queryset = StaffUserType.objects.filter(is_deleted=False)
    serializer_class = StaffUserTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "role-assigns"   
    AUDIT_ENDPOINT = "staff-user-type"
    
    permission_resource = "StaffUserType"

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=["get"], url_path="role-choices")
    def role_choices(self, request):
        user = request.user

        choices = StaffUserType.STAFF_ROLE_CHOICES

        if not user.is_superuser:
            choices = [c for c in choices if c[0] != "superadmin"]

        return Response([
            {"value": key, "label": label}
            for key, label in choices
        ])