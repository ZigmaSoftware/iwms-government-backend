from rest_framework import serializers
from app.models.role_assigns.contractorUserType import ContractorUserType
from app.validators.unique_name_validator import unique_name_validator


class ContractorUserTypeSerializer(serializers.ModelSerializer):
    usertype_name = serializers.CharField(
        source="usertype_id.name",
        read_only=True,
    )

    class Meta:
        model = ContractorUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate_usertype_id(self, usertype_obj):
        """Only allow ContractorUserType if UserType is 'contractor'."""
        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "contractor":
            raise serializers.ValidationError(
                "Contractor User Types can only be mapped to UserType = 'contractor'."
            )

        return usertype_obj

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["name"] = instance.get_name_display()
        return data

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=ContractorUserType,
            name_field="name",
        )(self, attrs)
