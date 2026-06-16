from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.user_creations.auditlog import AuditLog
from app.models.user_creations.staffcreation import Staffcreation
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreenaction import UserScreenAction


class AuditLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
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
            "company_id",
            "company_name",
            "project_id",
            "project_name",
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
