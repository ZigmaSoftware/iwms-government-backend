from rest_framework import viewsets, status
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet

from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.serializers.grivences.maincategory_serializer import MainCategorySerializer
from app.utils.audit_mixin import AuditViewSetMixin


class MainCategoryViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = MainCategory.objects.filter(is_deleted=False).order_by("unique_id")
    serializer_class = MainCategorySerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "grivences"
    AUDIT_ENDPOINT = "main-categories"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Main category deleted"}, status=status.HTTP_200_OK)
