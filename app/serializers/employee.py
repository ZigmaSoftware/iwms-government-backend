from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.user_creations.staffcreation import Staffcreation, StaffPersonalDetails
from app.models.user_creations.attendance import Employee
from django.conf import settings


class StaffPersonalSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = StaffPersonalDetails
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "dob",
            "blood_group",
            "marital_status",
            "gender",
            "present_address",
            "permanent_address",
        ]


class StaffOfficeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    personal = StaffPersonalSerializer(
        source="personal_details",
        read_only=True
    )
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Staffcreation
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "staff_unique_id",
            "emp_id",
            "employee_name",
            "department",
            "designation",
            "site_name",
            "doj",
            "photo",
            "personal",
        ]

    def get_photo(self, obj):
        """
        Fetch photo from Employee table using staff_unique_id (STRING)
        """
        emp = Employee.objects.filter(
            staff__staff_unique_id=obj.staff_unique_id
        ).first()

        if emp and emp.image_path:
            # Handle potential binary data
            if isinstance(emp.image_path, (bytes, bytearray, memoryview)):
                return None
            
            # If it's a string path, try to get URL
            if hasattr(emp.image_path, 'url'):
                return emp.image_path.url
            
            # If it's just a string path, return it
            return emp.image_path if emp.image_path else None

        return None
    
class StaffUpdateSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    dob = serializers.DateField(required=False)
    blood_group = serializers.CharField(required=False)
    photo = serializers.ImageField(required=False)

    class Meta:
        model = Staffcreation
        fields = [
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "employee_name",
            "department",
            "designation",
            "site_name",
            "dob",
            "blood_group",
            "photo",
        ]

    def update(self, instance, validated_data):
        image_file = validated_data.pop("photo", None)

        # Update staff core fields
        instance = super().update(instance, validated_data)

        # Update Employee image using staff_unique_id
        if image_file:
            emp = Employee.objects.filter(
                staff__staff_unique_id=instance.staff_unique_id
            ).first()

            if emp:
                emp.image_path = image_file
                emp.save(update_fields=["image_path"])

        return instance
