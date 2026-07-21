from rest_framework import serializers

from app.models.user_creations.staffcreation import StaffPersonalDetails, Staffcreation


class StaffPersonalSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffPersonalDetails
        fields = [
            "dob",
            "blood_group",
            "marital_status",
            "gender",
            "present_address",
            "permanent_address",
        ]


class StaffOfficeSerializer(serializers.ModelSerializer):
    personal = StaffPersonalSerializer(source="personal_details", read_only=True)

    class Meta:
        model = Staffcreation
        fields = [
            "staff_unique_id",
            "emp_id",
            "employee_name",
            "department",
            "designation",
            "doj",
            "photo",
            "attendance_reg_image",
            "personal",
        ]


class StaffUpdateSerializer(serializers.ModelSerializer):
    dob = serializers.DateField(required=False)
    blood_group = serializers.CharField(required=False)

    class Meta:
        model = Staffcreation
        fields = [
            "employee_name",
            "department",
            "designation",
            "dob",
            "blood_group",
            "photo",
            "attendance_reg_image",
        ]

    def update(self, instance, validated_data):
        validated_data.pop("dob", None)
        validated_data.pop("blood_group", None)
        return super().update(instance, validated_data)
