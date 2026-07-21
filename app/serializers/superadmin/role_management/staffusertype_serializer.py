from rest_framework import serializers
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.validators.unique_name_validator import unique_name_validator


class StaffUserTypeSerializer(serializers.ModelSerializer):
    # Extra field
    usertype_name = serializers.CharField(
        source="usertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []
    
    def validate_usertype_id(self, usertype_obj):
        """Only allow StaffUserType if UserType is 'staff'."""

        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "staff":
            raise serializers.ValidationError(
                "Staff User Types can only be mapped to UserType = 'staff'."
            )

        return usertype_obj
    

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=StaffUserType,
            name_field="name",
        )(self, attrs)
