from rest_framework import serializers
from django.db.models import Max
from app.models.core_modules.complaint_management.source_master import ComplaintSource
from app.models.core_modules.complaint_management.language_master import ComplaintLanguage
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.module_master import ComplaintModule
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from app.models.core_modules.complaint_management.sla_escalation_level import ComplaintSlaEscalationLevel
from app.serializers.superadmin.role_management.staffhierarchy_serializer import validated_scope
from app.utils.bare_id_keys import BareIdKeysMixin
from app.utils.staff_hierarchy import SCOPE_FIELDS, row_scope, scope_label, scope_level


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


class ComplaintModuleSerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintModule
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintCategorySerializer(BareIdKeysMixin, AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    default_priority_code = serializers.CharField(source="default_priority.priority_code", read_only=True)
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


class ComplaintSubcategorySerializer(BareIdKeysMixin, AutoSortOrderSerializerMixin, serializers.ModelSerializer):
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


class ComplaintSlaEscalationLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintSlaEscalationLevel
        fields = ["unique_id", "level", "is_enabled", "resolve_within_minutes"]
        read_only_fields = ["unique_id"]

    def validate_resolve_within_minutes(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Must be greater than 0.")
        return value


class ComplaintSlaRuleSerializer(BareIdKeysMixin, serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    # Per-Staff-Hierarchy-level resolve windows. Written wholesale on every
    # save: the incoming list replaces the rule's existing rows.
    escalation_levels = ComplaintSlaEscalationLevelSerializer(many=True, required=False)
    scope_label = serializers.SerializerMethodField()
    scope_level = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        read_only_fields = ["unique_id"]
        extra_kwargs = {
            field: {"required": False, "allow_null": True, "allow_blank": True}
            for field in SCOPE_FIELDS
        }

    def get_scope_label(self, obj):
        return scope_label(obj) or None

    def get_scope_level(self, obj):
        return scope_level(obj)

    def validate(self, attrs):
        scope = validated_scope(attrs, self.instance)
        for field in SCOPE_FIELDS:
            attrs[field] = scope.get(field)

        def current(field):
            return attrs[field] if field in attrs else getattr(self.instance, field, None)

        # One live rule per (category, sub-category, priority, source, place)
        # — two identical rules would make the winner arbitrary.
        others = ComplaintSlaRule.objects.filter(
            is_deleted=False,
            category_id=current("category_id"),
            subcategory_id=current("subcategory_id") or None,
            priority_id=current("priority_id"),
            source_id=current("source_id") or None,
        ).exclude(pk=getattr(self.instance, "pk", None))
        if any(row_scope(rule) == scope for rule in others):
            raise serializers.ValidationError(
                "An SLA rule for this category, priority, sub-category, source and location already exists."
            )
        return attrs

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

    def validate_escalation_levels(self, value):
        levels = [row["level"] for row in value]
        if len(levels) != len(set(levels)):
            raise serializers.ValidationError("Each hierarchy level can appear only once.")
        return value

    def create(self, validated_data):
        levels = validated_data.pop("escalation_levels", None)
        rule = super().create(validated_data)
        self._save_escalation_levels(rule, levels)
        self._reschedule(rule)
        return rule

    def update(self, instance, validated_data):
        levels = validated_data.pop("escalation_levels", None)
        rule = super().update(instance, validated_data)
        self._save_escalation_levels(rule, levels)
        self._reschedule(rule)
        return rule

    @staticmethod
    def _reschedule(rule):
        """New timings apply to tickets already in flight, not just new ones."""
        from django.db import transaction
        from app.services.complaint_escalation import reschedule_open_tickets

        transaction.on_commit(lambda: reschedule_open_tickets(rule))

    def _save_escalation_levels(self, rule, levels):
        if levels is None:
            return
        rule.escalation_levels.update(is_deleted=True, is_active=False)
        ComplaintSlaEscalationLevel.objects.bulk_create(
            ComplaintSlaEscalationLevel(
                sla_rule_id=rule.unique_id,
                level=row["level"],
                is_enabled=row.get("is_enabled", True),
                resolve_within_minutes=row["resolve_within_minutes"],
            )
            for row in levels
        )
