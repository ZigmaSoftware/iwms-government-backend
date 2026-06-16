from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.user_creations.loginAudit import LoginAudit


class LoginAuditSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = LoginAudit
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "user_unique_id",
            "username",
            "password",
            "ip_address",
            "user_agent",
            "success",
            "reason",
            "timestamp",
        ]
        read_only_fields = ["unique_id", "timestamp"]
        extra_kwargs = {
            "password": {"write_only": True, "required": False, "allow_null": True},
        }
