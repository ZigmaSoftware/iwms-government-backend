from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.decorators import action
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.serializers.role_assigns.governmentstaffusertype_serializer import GovernmentStaffUserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class GovernmentStaffUserTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = GovernmentStaffUserType.objects.filter(is_deleted=False)
    serializer_class = GovernmentStaffUserTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "government-staff-user-type"

    permission_resource = "GovernmentStaffUserType"

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=False, methods=["get"], url_path="role-choices")
    def role_choices(self, request):
        level = request.query_params.get("level")
        choices = GovernmentStaffUserType.GOVT_ROLE_CHOICES
        if level:
            all_levels = [key for key, _ in GovernmentStaffUserType.GOVT_LEVEL_CHOICES]
            prefix = f"govt_{level}_"
            other_prefixes = [
                f"govt_{other}_" for other in all_levels
                if other != level and other.startswith(level)
            ]
            choices = [
                (key, label) for key, label in choices
                if key.startswith(prefix)
                and not any(key.startswith(p) for p in other_prefixes)
            ]
        return Response([
            {"value": key, "label": label}
            for key, label in choices
        ])

    @action(detail=False, methods=["get"], url_path="level-choices")
    def level_choices(self, request):
        return Response([
            {"value": key, "label": label}
            for key, label in GovernmentStaffUserType.GOVT_LEVEL_CHOICES
        ])

    @action(detail=False, methods=["get"], url_path="by-level")
    def by_level(self, request):
        level = request.query_params.get("level")
        qs = self.get_queryset()
        if level:
            qs = qs.filter(level=level)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
