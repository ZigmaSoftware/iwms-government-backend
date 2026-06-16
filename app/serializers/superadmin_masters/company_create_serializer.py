# from rest_framework import serializers

# from app.models.superadmin_masters.company import Company


# class PlatformCompanyCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Company
#         fields = ["unique_id", "name", "description", "is_active"]
#         read_only_fields = ["unique_id"]

#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         view = self.context.get("view")
#         if view and getattr(view, "action", None) == "create":
#             return {"company": data}
#         return data

#     def update(self, instance, validated_data):
#         # Keep legacy behavior: PUT without description clears description.
#         if not self.partial and "description" not in validated_data:
#             validated_data["description"] = None
#         return super().update(instance, validated_data)


# class CompanySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Company
#         fields = ["unique_id", "name", "description", "is_active"]
#         read_only_fields = ["unique_id"]



from rest_framework import serializers
from app.models.superadmin_masters.company import Company


class PlatformCompanyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["unique_id", "name", "description", "company_logo", "is_active"]
        read_only_fields = ["unique_id"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get("view")

        # Wrap response only for create action
        if view and getattr(view, "action", None) == "create":
            return {"company": data}

        return data

    def update(self, instance, validated_data):
        # Legacy behavior: PUT without description clears description
        if not self.partial and "description" not in validated_data:
            validated_data["description"] = None

        return super().update(instance, validated_data)


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["unique_id", "name", "description", "company_logo", "is_active"]
        read_only_fields = ["unique_id"]
