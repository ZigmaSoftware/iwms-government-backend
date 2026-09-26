from rest_framework import serializers
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.utils import ref_cache
from app.validators.unique_name_validator import unique_name_validator


class GovernmentStaffUserTypeSerializer(serializers.ModelSerializer):
    usertype_id = serializers.CharField()
    usertype_name = serializers.SerializerMethodField()
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

    def get_usertype_name(self, obj):
        return getattr(obj.usertype, "name", None)

    def validate_usertype_id(self, usertype_id):
        """Only allow GovernmentStaffUserType if UserType is 'government'."""
        usertype_obj = ref_cache.get(UserType, usertype_id)
        if not usertype_obj:
            raise serializers.ValidationError("Invalid UserType.")
        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")
        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")
        if usertype_obj.name.lower().strip() != "government":
            raise serializers.ValidationError(
                "Government Staff User Types can only be mapped to UserType = 'government'."
            )
        return usertype_id

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=GovernmentStaffUserType,
            name_field="name",
        )(self, attrs)
