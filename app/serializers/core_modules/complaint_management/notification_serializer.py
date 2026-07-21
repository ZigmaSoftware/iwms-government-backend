from rest_framework import serializers
from app.models.core_modules.complaint_management.notification import ComplaintNotification


class ComplaintNotificationSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)
    ticket_status_code = serializers.CharField(source="ticket.status.status_code", read_only=True)
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = ComplaintNotification
        fields = [
            "unique_id",
            "ticket",
            "ticket_no",
            "ticket_status_code",
            "event_type",
            "event_type_display",
            "title",
            "message",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
