from rest_framework import serializers
from django.db.models import Max
from app.models.core_modules.complaint_management.source_master import ComplaintSource
from app.models.core_modules.complaint_management.language_master import ComplaintLanguage
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.module_master import ComplaintModule
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule


class AutoSortOrderSerializerMixin:
    def create(self, validated_data):
        if "sort_order" not in validated_data:
            max_order = self.Meta.model.objects.aggregate(max_order=Max("sort_order"))["max_order"] or 0
            validated_data["sort_order"] = max_order + 1
        return super().create(validated_data)


class ComplaintSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintSource
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintLanguage
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintPrioritySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintPriority
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintStatusSerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintStatus
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintTeamSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    lead_staff_name = serializers.CharField(source="lead_staff.employee_name", read_only=True)
    escalates_to_name = serializers.CharField(source="escalates_to.team_name", read_only=True)
    escalates_to_code = serializers.CharField(source="escalates_to.team_code", read_only=True)

    class Meta:
        model = ComplaintTeam
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def validate_department_id(self, value):
        if not value:
            return value
        from app.models.masters.department import Department

        if not Department.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid department.")
        return value

    def validate_lead_staff_id(self, value):
        if not value:
            return value
        from app.models.superadmin.staff_management.staffcreation import (
            StaffcreationOfficeDetails,
        )

        if not StaffcreationOfficeDetails.objects.filter(staff_unique_id=value).exists():
            raise serializers.ValidationError("Invalid staff.")
        return value

    def validate_escalates_to_id(self, value):
        if not value:
            return value
        if not ComplaintTeam.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid team.")
        return value


class ComplaintModuleSerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintModule
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintCategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    default_priority_code = serializers.CharField(source="default_priority.priority_code", read_only=True)
    default_team_name = serializers.CharField(source="default_team.team_name", read_only=True)
    module_code = serializers.CharField(source="module.module_code", read_only=True)
    module_name = serializers.CharField(source="module.module_name", read_only=True)

    class Meta:
        model = ComplaintCategory
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]

    def validate_module_id(self, value):
        if value and not ComplaintModule.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid module.")
        return value

    def validate_default_priority_id(self, value):
        if value and not ComplaintPriority.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid priority.")
        return value

    def validate_default_team_id(self, value):
        if value and not ComplaintTeam.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid team.")
        return value


class ComplaintSubcategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)

    class Meta:
        model = ComplaintSubcategory
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]

    def validate_category_id(self, value):
        if not value:
            raise serializers.ValidationError("This field is required.")
        if not ComplaintCategory.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid category.")
        return value

    def validate_default_priority_id(self, value):
        if value and not ComplaintPriority.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid priority.")
        return value


class ComplaintSlaRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def validate_category_id(self, value):
        if not value:
            raise serializers.ValidationError("This field is required.")
        if not ComplaintCategory.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid category.")
        return value

    def validate_priority_id(self, value):
        if not value:
            raise serializers.ValidationError("This field is required.")
        if not ComplaintPriority.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid priority.")
        return value

    def validate_subcategory_id(self, value):
        if value and not ComplaintSubcategory.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid subcategory.")
        return value

    def validate_source_id(self, value):
        if value and not ComplaintSource.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid source.")
        return value

    def validate_escalation_team_id(self, value):
        if value and not ComplaintTeam.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid team.")
        return value
