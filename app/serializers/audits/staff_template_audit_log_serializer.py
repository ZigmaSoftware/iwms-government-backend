from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

from app.models.audits.staff_template_audit_log import StaffTemplateAuditLog


class StaffTemplateAuditLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    performed_by = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        read_only=True,
    )
    performed_by_name = serializers.CharField(
        source="performed_by.employee_name",
        read_only=True,
    )

    class Meta:
        model = StaffTemplateAuditLog
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "unique_id",
            "entity_type",
            "entity_id",
            "action",
            "performed_by",
            "performed_by_name",
            "performed_role",
            "change_remarks",
            "performed_at",
        ]
        read_only_fields = fields
