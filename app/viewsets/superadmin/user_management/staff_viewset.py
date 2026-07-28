from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.response import Response
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.serializers.superadmin.user_management.user_serializer import StaffSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class StaffViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Staffcreation.objects.filter(is_deleted=False)
    serializer_class = StaffSerializer
    lookup_field = "staff_unique_id"
    permission_resource = "UsersCreation"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staffs"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Staff soft deleted successfully"}, status=status.HTTP_200_OK)
