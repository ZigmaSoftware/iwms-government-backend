from rest_framework import serializers

from app.models.superadmin.audits.audit_log import AuditLog
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.utils import ref_cache


class AuditLogSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mainscreen_id = serializers.CharField()
    userscreen_id = serializers.CharField()
    userscreenaction_id = serializers.CharField()

    user_name = serializers.SerializerMethodField()
    staffusertype_name = serializers.SerializerMethodField()
    mainscreen_name = serializers.SerializerMethodField()
    userscreen_name = serializers.SerializerMethodField()
    userscreenaction_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "unique_id",
            "user_id",
            "user_name",
            "staffusertype_id",
            "staffusertype_name",
            "mainscreen_id",
            "mainscreen_name",
            "userscreen_id",
            "userscreen_name",
            "userscreenaction_id",
            "userscreenaction_name",
            "success",
            "reason",
            "ip_address",
            "user_agent",
            "timestamp",
        ]
        read_only_fields = ["unique_id", "timestamp"]

    def get_user_name(self, obj):
        return getattr(obj.user, "employee_name", None)

    def get_staffusertype_name(self, obj):
        return getattr(obj.staffusertype, "name", None)

    def get_mainscreen_name(self, obj):
        return getattr(obj.mainscreen, "mainscreen_name", None)

    def get_userscreen_name(self, obj):
        return getattr(obj.userscreen, "userscreen_name", None)

    def get_userscreenaction_name(self, obj):
        return getattr(obj.userscreenaction, "action_name", None)
