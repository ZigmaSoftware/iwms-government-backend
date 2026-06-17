from app.models.customers.userchargerule import UserChargeRule
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
            "property_id",
            "subproperty_id",
        )
        .order_by("unique_id")
    )
