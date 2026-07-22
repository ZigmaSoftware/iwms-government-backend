from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.decorators import action
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.serializers.superadmin.role_management.contractorusertype_serializer import ContractorUserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class ContractorUserTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ContractorUserType.objects.filter(is_deleted=False)
    serializer_class = ContractorUserTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "contractor-user-type"

    permission_resource = "ContractorUserType"

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=["get"], url_path="role-choices")
    def role_choices(self, request):
        user = request.user

        choices = ContractorUserType.CONTRACTOR_ROLE_CHOICES

        # 🔐 Optional: restrict roles based on logged-in user
        if not user.is_superuser:
            choices = [c for c in choices if c[0] != "superadmin"]
        return Response([
            {"value": key, "label": label}
            for key, label in ContractorUserType.CONTRACTOR_ROLE_CHOICES
        ])
