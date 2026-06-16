from app.models.customers.userchargerule import UserChargeRule
from app.models.superadmin_masters.project import Project
from app.serializers.customers.userchargerule_serializer import UserChargeRuleSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class UserChargeRuleViewSet(CompanyScopedViewSet):
    permission_resource = "UserChargeRule"
    serializer_class = UserChargeRuleSerializer
    lookup_field = "unique_id"

    queryset = (
        UserChargeRule.objects
        .filter(is_deleted=False)
        .select_related(
            "company_id",
            "project_id",
            "property_id",
            "subproperty_id",
        )
        .order_by("unique_id")
    )

    def _resolve_default_project(self):
        company = self._company()
        if not company:
            return None

        user = getattr(self.request, "user", None)
        user_project = getattr(user, "project_id", None)

        if user_project and getattr(user_project, "company_id", None) == company:
            return user_project

        payload = getattr(self.request, "jwt_payload", {}) or {}
        project_unique_id = payload.get("project_unique_id")

        if not project_unique_id:
            return None

        return Project.objects.filter(
            unique_id=project_unique_id,
            company_id=company,
        ).first()

    def _project(self):
        project = super()._project()

        if project is not None:
            return project

        if self.request.method in ("POST", "PUT", "PATCH"):
            return self._resolve_default_project()

        return None
