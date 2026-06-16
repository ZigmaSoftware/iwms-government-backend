from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.role_assigns.userType import UserType
from app.validators.unique_name_validator import unique_name_validator
class UserTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    company_name = serializers.CharField(source="company_id.name", read_only=True)
    project_name = serializers.CharField(source="project_id.name", read_only=True)
    class Meta:
        model = UserType
        fields = [
            "unique_id",
            "name",
            "company_id",
            "project_id",
            "company_name",
            "project_name",
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
