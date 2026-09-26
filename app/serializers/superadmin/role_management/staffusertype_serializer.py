from rest_framework import serializers
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.utils import ref_cache
from app.validators.unique_name_validator import unique_name_validator


class StaffUserTypeSerializer(serializers.ModelSerializer):
    usertype_id = serializers.CharField()
    usertype_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def get_usertype_name(self, obj):
        return getattr(obj.usertype, "name", None)

    def validate_usertype_id(self, usertype_id):
        """Only allow StaffUserType if UserType is 'staff'."""
        usertype_obj = ref_cache.get(UserType, usertype_id)
        if not usertype_obj:
            raise serializers.ValidationError("Invalid UserType.")
        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")
        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")
        if usertype_obj.name.lower().strip() != "staff":
            raise serializers.ValidationError(
                "Staff User Types can only be mapped to UserType = 'staff'."
            )
        return usertype_id

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=StaffUserType,
            name_field="name",
        )(self, attrs)
