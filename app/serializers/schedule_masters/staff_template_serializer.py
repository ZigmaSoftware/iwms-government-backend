from rest_framework import serializers
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(serializers.ModelSerializer):

    driver_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    operator_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )




    approved_by = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True
    )

    driver_name = serializers.CharField(source="driver_id.employee_name", read_only=True)
    operator_name = serializers.CharField(source="operator_id.employee_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.employee_name", read_only=True)

    extra_operator_id = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False
    )

    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffTemplate
        fields = [
            "unique_id",

            "display_code",

            "driver_id",
            "driver_name",
            # "driver_role",

            "operator_id",
            "operator_name",
            # "operator_role",

            "extra_operator_id",

            "staffusertype_name",

            "created_by",
            

            "updated_by",
        

            "approved_by",
            "approved_by_name",

            "status",
            "approval_status",

            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
            "driver_name",
            "operator_name",
            "driver_role",
            "operator_role",
            "created_by_name",
            "updated_by_name",
            "approved_by_name",
        ]

    def validate_approved_by(self, value):
        if self.instance and self.instance.approved_by:
            raise serializers.ValidationError("Approved by cannot be modified")
        return value