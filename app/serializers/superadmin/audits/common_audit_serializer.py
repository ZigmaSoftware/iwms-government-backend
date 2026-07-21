from rest_framework import serializers
from app.utils.common_audit import CommonAudit


class CommonAuditSerializer(serializers.ModelSerializer):

    class Meta:
        model = CommonAudit
        fields = "__all__"
        read_only_fields = ("uuid", "createdBy", "createdAt")
