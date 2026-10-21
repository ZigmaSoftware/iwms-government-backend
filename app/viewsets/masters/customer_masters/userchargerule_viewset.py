from rest_framework import viewsets

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.customer_masters.userchargerule import UserChargeRule
from app.serializers.masters.customer_masters.userchargerule_serializer import UserChargeRuleSerializer

USER_CHARGE_RULE_CACHE_SCOPES = ("user_charge_rule_list", "user_charge_rule_detail")


class UserChargeRuleViewSet(viewsets.ModelViewSet):
    throttle_scope = "user_charge_rule"
    permission_resource = "UserChargeRule"
    serializer_class = UserChargeRuleSerializer
    lookup_field = "unique_id"

    queryset = (
        UserChargeRule.objects
        .filter(is_deleted=False)
        .order_by("unique_id")
    )

    @cache_api("user_charge_rule_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("user_charge_rule_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*USER_CHARGE_RULE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*USER_CHARGE_RULE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*USER_CHARGE_RULE_CACHE_SCOPES)
