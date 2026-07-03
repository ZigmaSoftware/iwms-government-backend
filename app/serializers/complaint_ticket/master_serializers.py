from rest_framework import serializers
from app.models.complaint_ticket.source_master import ComplaintSource
from app.models.complaint_ticket.language_master import ComplaintLanguage
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.status_master import ComplaintStatus
from app.models.complaint_ticket.team_master import ComplaintTeam
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.sla_rule_master import ComplaintSlaRule


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


class ComplaintPrioritySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintPriority
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintStatus
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintTeamSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    lead_staff_name = serializers.CharField(source="lead_staff.employee_name", read_only=True)
    escalates_to_name = serializers.CharField(source="escalates_to.team_name", read_only=True)
    escalates_to_code = serializers.CharField(source="escalates_to.team_code", read_only=True)

    class Meta:
        model = ComplaintTeam
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintCategorySerializer(serializers.ModelSerializer):
    default_priority_code = serializers.CharField(source="default_priority.priority_code", read_only=True)
    default_team_name = serializers.CharField(source="default_team.team_name", read_only=True)

    class Meta:
        model = ComplaintCategory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintSubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)

    class Meta:
        model = ComplaintSubcategory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintSlaRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        read_only_fields = ["unique_id"]
