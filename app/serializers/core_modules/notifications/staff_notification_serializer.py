from rest_framework import serializers

from app.models.core_modules.notifications.staff_notification import StaffNotification


class StaffNotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source="get_notification_type_display", read_only=True
    )

    class Meta:
        model = StaffNotification
        fields = [
            "unique_id",
            "notification_type",
            "notification_type_display",
            "title",
            "message",
            "data",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
