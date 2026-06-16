from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from app.permissions.platform import PlatformOrCompanyAdminOnly
from app.models.superadmin_masters.company import Company
from app.serializers.superadmin_masters.company_create_serializer import (
    CompanySerializer,
    PlatformCompanyCreateSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin

class PlatformCompanyCreateViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [PlatformOrCompanyAdminOnly]
    serializer_class = CompanySerializer
    lookup_field = "unique_id"
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    AUDIT_MODULE = "superadmin-masters"
    AUDIT_ENDPOINT = "companies"

    # 🔹 Role-Based Queryset
    def get_queryset(self):
        user = self.request.user

        # Platform super admin (is_superuser=True and no company)
        if getattr(user, "is_superuser", False) and getattr(user, "company_id", None) is None:
            return Company.objects.filter(is_deleted=False).order_by("name")

        # Company admin — full read access to their company
        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        user_company = getattr(user, "company_id", None)

        if user_company is not None and (role or "").lower() in ("admin", "company admin"):
            return Company.objects.filter(
                unique_id=user_company.unique_id,
                is_deleted=False,
            )

        # Any other authenticated user that belongs to a company:
        # allow read-only retrieval of their own company so the frontend
        # can resolve the company label (lookup by unique_id in the URL).
        if user_company is not None:
            return Company.objects.filter(
                unique_id=user_company.unique_id,
                is_deleted=False,
            )

        return Company.objects.none()
    # 🔹 Restrict Modify Access
    def get_permissions(self):
        user = self.request.user

        if getattr(user, "role", None) == "admin" and self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            raise PermissionDenied("Admins are not allowed to modify companies.")

        return super().get_permissions()

    # 🔹 Dynamic Serializer
    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PlatformCompanyCreateSerializer
        return CompanySerializer

    # 🔹 Safe Object Fetch
    def get_object(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        unique_id = self.kwargs.get(lookup_url_kwarg)

        company = self.get_queryset().filter(unique_id=unique_id).first()
        if not company:
            raise NotFound("Company not found")

        return company
