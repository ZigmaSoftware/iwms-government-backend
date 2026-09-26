from rest_framework import serializers
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache

class CountrySerializer(serializers.ModelSerializer):
    continent_name = serializers.SerializerMethodField()

    def get_continent_name(self, obj):
        return getattr(ref_cache.get(Continent, obj.continent_id, "unique_id"), "name", None)

    class Meta:
        model = Country
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Country,
            scope_fields=["continent_id"]
        )(self, attrs)
