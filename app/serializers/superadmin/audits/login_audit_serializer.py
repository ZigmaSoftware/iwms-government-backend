from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.serializers.superadmin.audits.common_audit_serializer import geo_display
from app.utils import ref_cache
from app.utils.audit_context import display_name

# Account model each login module authenticates against, keyed by
# LoginAudit.module_name; (model, lookup field) for ref_cache.
ACCOUNT_MODELS_BY_MODULE = {
    "customer": (CustomerCreation, "unique_id"),
    "panchayat_leader": (PanchayatLeaderLogin, "unique_id"),
    "district_leader": (DistrictLeaderLogin, "unique_id"),
    "state_leader": (StateLeaderLogin, "unique_id"),
}
# Staff/government/contractor logins and anything unrecognised ("auto",
# "platform") resolve against staff first, then platform users.
FALLBACK_ACCOUNT_MODELS = (
    (Staffcreation, "staff_unique_id"),
    (User, "unique_id"),
)


def login_account(audit):
    """The account a login row belongs to, or None (failed attempts carry no
    user_unique_id)."""
    if not audit.user_unique_id:
        return None
    candidates = []
    if audit.module_name in ACCOUNT_MODELS_BY_MODULE:
        candidates.append(ACCOUNT_MODELS_BY_MODULE[audit.module_name])
    candidates.extend(FALLBACK_ACCOUNT_MODELS)
    for model, field in candidates:
        account = ref_cache.get(model, audit.user_unique_id, field)
        if account is not None:
            return account
    return None


class LoginAuditSerializer(serializers.ModelSerializer):
    # Who logged in and where they sit in the geo hierarchy — the government
    # counterpart of the company/project the private trail resolves, so a
    # row reads as a person in a local body rather than a bare id.
    user_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    local_body_name = serializers.SerializerMethodField()
    local_body_level = serializers.SerializerMethodField()

    class Meta:
        model = LoginAudit
        fields = [
            "unique_id",
            "user_unique_id",
            "user_name",
            "module_name",
            "username",
            "password",
            "ip_address",
            "user_agent",
            "success",
            "reason",
            "timestamp",
            "district_name",
            "local_body_name",
            "local_body_level",
        ]
        read_only_fields = ["unique_id", "timestamp"]
        extra_kwargs = {
            "password": {"write_only": True, "required": False, "allow_null": True},
        }

    def _resolved(self, obj):
        cache = getattr(self, "_account_cache", None)
        if cache is None:
            cache = self._account_cache = {}
        if obj.pk not in cache:
            account = login_account(obj)
            cache[obj.pk] = {
                "user_name": display_name(account) if account is not None else None,
                **geo_display(account),
            }
        return cache[obj.pk]

    def get_user_name(self, obj):
        return self._resolved(obj)["user_name"]

    def get_district_name(self, obj):
        return self._resolved(obj)["district_name"]

    def get_local_body_name(self, obj):
        return self._resolved(obj)["local_body_name"]

    def get_local_body_level(self, obj):
        return self._resolved(obj)["local_body_level"]
