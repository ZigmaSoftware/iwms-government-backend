from rest_framework import serializers

from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.staffHierarchy import StaffHierarchy
from app.utils import ref_cache
from app.utils.staff_hierarchy import (
    LOCAL_BODY_SCOPE_FIELDS,
    PARENT_FIELDS,
    SCOPE_FIELDS,
    can_report_to,
    complete_geo,
    level_within,
    find_cycle,
    row_scope,
    scope_label,
    scope_level,
    scope_government_level,
    scope_record,
)


def validated_scope(attrs, instance=None):
    """A scoped row's location after this request: given values over the
    stored ones, blanks dropped, parents filled in from the narrowest level.
    Shared by every model with the Staff Hierarchy scope columns."""
    scope = {}
    for field in SCOPE_FIELDS:
        if field in attrs:
            value = attrs[field]
        else:
            value = getattr(instance, field, None)
        if value:
            scope[field] = value

    local_bodies = [field for field in LOCAL_BODY_SCOPE_FIELDS if scope.get(field)]
    if len(local_bodies) > 1:
        raise serializers.ValidationError("Select only one local body.")

    for field, value in scope.items():
        record = scope_record(field, value)
        if record is None or getattr(record, "is_deleted", False):
            raise serializers.ValidationError({field: "Invalid selection."})
        for parent in PARENT_FIELDS.get(field, ()):
            parent_value = getattr(record, parent, None)
            if scope.get(parent) and parent_value and parent_value != scope[parent]:
                raise serializers.ValidationError(
                    {field: "Does not belong to the selected parent location."}
                )

    # Parent values the local body/district implied are stored too, so the
    # scope columns always describe a consistent chain.
    return complete_geo(scope)


class StaffHierarchySerializer(serializers.ModelSerializer):
    governmentusertype_id = serializers.CharField()
    reports_to_governmentusertype_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    governmentusertype_name = serializers.SerializerMethodField()
    governmentusertype_level = serializers.SerializerMethodField()
    reports_to_governmentusertype_name = serializers.SerializerMethodField()
    reports_to_governmentusertype_level = serializers.SerializerMethodField()
    scope_label = serializers.SerializerMethodField()
    scope_level = serializers.SerializerMethodField()

    class Meta:
        model = StaffHierarchy
        fields = "__all__"
        read_only_fields = ["unique_id", "created_at", "updated_at"]
        # (role, scope) uniqueness among active rows is enforced in
        # validate(); NULL scope columns rule out a DB unique constraint.
        validators = []
        extra_kwargs = {
            field: {"required": False, "allow_null": True, "allow_blank": True}
            for field in SCOPE_FIELDS
        }

    @staticmethod
    def _role(role_id):
        return ref_cache.get(GovernmentStaffUserType, role_id)

    def get_governmentusertype_name(self, obj):
        role = self._role(obj.governmentusertype_id)
        return role.get_name_display() if role else None

    def get_governmentusertype_level(self, obj):
        role = self._role(obj.governmentusertype_id)
        return role.get_level_display() if role else None

    def get_reports_to_governmentusertype_name(self, obj):
        role = self._role(obj.reports_to_governmentusertype_id)
        return role.get_name_display() if role else None

    def get_reports_to_governmentusertype_level(self, obj):
        role = self._role(obj.reports_to_governmentusertype_id)
        return role.get_level_display() if role else None

    def get_scope_label(self, obj):
        return scope_label(obj) or None

    def get_scope_level(self, obj):
        return scope_level(obj)

    def _validate_role(self, role_id):
        role = self._role(role_id)
        if not role or role.is_deleted:
            raise serializers.ValidationError("Invalid Government Staff User Type.")
        return role_id

    def validate_governmentusertype_id(self, value):
        return self._validate_role(value)

    def validate_reports_to_governmentusertype_id(self, value):
        if not value:
            return None
        return self._validate_role(value)

    def validate(self, attrs):
        role = attrs.get(
            "governmentusertype_id",
            getattr(self.instance, "governmentusertype_id", None),
        )
        reports_to = attrs.get(
            "reports_to_governmentusertype_id",
            getattr(self.instance, "reports_to_governmentusertype_id", None),
        )
        instance_pk = getattr(self.instance, "pk", None)

        if reports_to and reports_to == role:
            raise serializers.ValidationError(
                "A staff user type cannot report to itself."
            )

        scope = validated_scope(attrs, self.instance)
        for field in SCOPE_FIELDS:
            attrs[field] = scope.get(field)

        role_obj = self._role(role)
        scope_level = scope_government_level(scope)
        if role_obj and not level_within(role_obj.level, scope_level):
            raise serializers.ValidationError({
                "governmentusertype_id": (
                    f"A {role_obj.get_level_display()} role cannot be configured for a "
                    f"{dict(GovernmentStaffUserType.GOVT_LEVEL_CHOICES)[scope_level]} location."
                )
            })
        head_obj = self._role(reports_to)
        if role_obj and head_obj and not can_report_to(role_obj.level, head_obj.level):
            raise serializers.ValidationError({
                "reports_to_governmentusertype_id": (
                    f"A {role_obj.get_level_display()} role can only report to a role at the "
                    "same level or a broader one."
                )
            })

        others = list(
            StaffHierarchy.objects.filter(is_deleted=False).exclude(pk=instance_pk)
        )
        duplicate = any(
            row.governmentusertype_id == role and row_scope(row) == scope
            for row in others
        )
        if duplicate:
            raise serializers.ValidationError(
                {"governmentusertype_id": "A hierarchy entry for this role and location already exists."}
            )

        pending = StaffHierarchy(
            governmentusertype_id=role,
            reports_to_governmentusertype_id=reports_to,
            **{field: scope.get(field) for field in SCOPE_FIELDS},
        )
        if reports_to and find_cycle(others + [pending], pending):
            raise serializers.ValidationError(
                "This mapping creates a reporting cycle."
            )

        return attrs
