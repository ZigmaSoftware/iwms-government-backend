from rest_framework import serializers
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.validators.unique_name_validator import unique_name_validator

class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = [
            "unique_id",
            "main_categoryName",
            "is_active"
        ]
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=MainCategory,
            name_field="main_categoryName",
        )(self, attrs)
