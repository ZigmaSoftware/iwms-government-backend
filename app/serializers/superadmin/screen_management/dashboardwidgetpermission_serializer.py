from rest_framework import serializers

from app.models.superadmin.screen_management.dashboardwidgetpermission import DashboardWidgetPermission


class DashboardWidgetPermissionSerializer(serializers.ModelSerializer):
    widgetName = serializers.CharField(source="widget_name", required=False)
    isEnabled = serializers.BooleanField(source="is_enabled", required=False)
    orderNo = serializers.IntegerField(source="order_no", required=False)

    class Meta:
        model = DashboardWidgetPermission
        fields = "__all__"
