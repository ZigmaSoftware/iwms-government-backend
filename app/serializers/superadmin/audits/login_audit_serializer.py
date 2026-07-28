from rest_framework import serializers

from app.models.superadmin.audits.login_audit import LoginAudit


class LoginAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginAudit
        fields = [
            "unique_id",
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
