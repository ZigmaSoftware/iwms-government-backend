from rest_framework import serializers
from app.models.audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from app.models.user_creations.staffcreation import Staffcreation


class SupervisorZoneAccessAuditSerializer(serializers.ModelSerializer):
    unique_id = serializers.CharField(read_only=True)
    supervisor_id = serializers.SlugRelatedField(
        source="supervisor",
        slug_field="staff_unique_id",
        read_only=True
    )

    performed_by = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        read_only=True
    )

    class Meta:
        model = SupervisorZoneAccessAudit
        fields = [
            "unique_id",
            "supervisor_id",
            "old_zone_ids",
            "new_zone_ids",
            "performed_by",
            "performed_role",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields
