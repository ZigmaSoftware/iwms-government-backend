from rest_framework import viewsets

from app.models.masters.customer_masters.userchargerule import UserChargeRule
from app.serializers.masters.customer_masters.userchargerule_serializer import UserChargeRuleSerializer


class UserChargeRuleViewSet(viewsets.ModelViewSet):
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
