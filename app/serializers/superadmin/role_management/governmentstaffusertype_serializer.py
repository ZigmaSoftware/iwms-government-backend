from rest_framework import serializers
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.validators.unique_name_validator import unique_name_validator


class GovernmentStaffUserTypeSerializer(serializers.ModelSerializer):
    usertype_name = serializers.CharField(
        source="usertype_id.name",
        read_only=True,
    )
    level_display = serializers.CharField(
        source="get_level_display",
        read_only=True,
    )
    name_display = serializers.CharField(
        source="get_name_display",
        read_only=True,
    )

    class Meta:
        model = GovernmentStaffUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate_usertype_id(self, usertype_obj):
        """Only allow GovernmentStaffUserType if UserType is 'government'."""
        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "government":
            raise serializers.ValidationError(
                "Government Staff User Types can only be mapped to UserType = 'government'."
            )

        return usertype_obj

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=GovernmentStaffUserType,
            name_field="name",
        )(self, attrs)
