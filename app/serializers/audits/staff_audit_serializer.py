from rest_framework import serializers
from app.models.audits.staff_audit import StaffAudit


class StaffAuditSerializer(serializers.ModelSerializer):

    class Meta:
        model = StaffAudit
        fields = "__all__"
        read_only_fields = ("uuid", "createdBy", "createdAt")
