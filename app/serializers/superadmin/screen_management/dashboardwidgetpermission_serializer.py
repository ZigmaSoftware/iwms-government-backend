from rest_framework import serializers

from app.models.superadmin.screen_management.dashboardwidgetpermission import DashboardWidgetPermission
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.utils import ref_cache


class DashboardWidgetPermissionSerializer(serializers.ModelSerializer):
    widgetName = serializers.CharField(source="widget_name", required=False)
    isEnabled = serializers.BooleanField(source="is_enabled", required=False)
    orderNo = serializers.IntegerField(source="order_no", required=False)

    usertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    governmentusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    usertype_name = serializers.SerializerMethodField()
    staffusertype_name = serializers.SerializerMethodField()
    contractorusertype_name = serializers.SerializerMethodField()
    governmentusertype_name = serializers.SerializerMethodField()

    class Meta:
        model = DashboardWidgetPermission
        fields = "__all__"

    def get_usertype_name(self, obj):
        return getattr(obj.usertype, "name", None)

    def get_staffusertype_name(self, obj):
        return getattr(obj.staffusertype, "name", None)

    def get_contractorusertype_name(self, obj):
        return getattr(obj.contractorusertype, "name", None)

    def get_governmentusertype_name(self, obj):
        return getattr(obj.governmentusertype, "name", None)
