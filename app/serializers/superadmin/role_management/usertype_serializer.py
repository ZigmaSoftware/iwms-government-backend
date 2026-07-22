from rest_framework import serializers
from app.models.superadmin.role_management.userType import UserType
from app.validators.unique_name_validator import unique_name_validator
class UserTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserType
        fields = [
            "unique_id",
            "name",
            "is_active",
            "is_deleted",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id"]  
        validators = []
    def validate(self, attrs):
        return unique_name_validator(
            Model=UserType,
            name_field="name",
        )(self, attrs)
