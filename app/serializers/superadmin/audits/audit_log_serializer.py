from rest_framework import serializers

from app.models.superadmin.audits.audit_log import AuditLog
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction


class AuditLogSerializer(serializers.ModelSerializer):
    user_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.all(),
    )

    staffusertype_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=StaffUserType.objects.all(),
        required=False,
        allow_null=True,
    )

    mainscreen_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=MainScreen.objects.all(),
    )

    userscreen_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=UserScreen.objects.all(),
    )

    userscreenaction_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=UserScreenAction.objects.all(),
    )

    class Meta:
        model = AuditLog
        fields = [
            "unique_id",
            "user_id",
            "staffusertype_id",
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
            "success",
            "reason",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = ["unique_id", "timestamp"]
