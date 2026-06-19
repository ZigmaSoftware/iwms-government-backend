from rest_framework import serializers

from app.models.schedule_masters.collection_point import Collection_point
from app.validators.unique_name_validator import unique_name_validator
from app.utils.hierarchy import validate_single_hierarchy


class CollectionPointSerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)
    corporation_name = serializers.CharField(source="corporation_id.corporation_name", read_only=True)
    municipality_name = serializers.CharField(source="municipality_id.municipality_name", read_only=True)
    town_panchayat_name = serializers.CharField(source="town_panchayat_id.town_panchayat_name", read_only=True)
    panchayat_union_name = serializers.CharField(source="panchayat_union_id.union_name", read_only=True)

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "corporation_id",
            "corporation_name",
            "municipality_id",
            "municipality_name",
            "town_panchayat_id",
            "town_panchayat_name",
            "panchayat_union_id",
            "panchayat_union_name",
            "panchayat_id",
            "panchayat_name",
            "cp_name",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def validate(self, attrs):
        validate_single_hierarchy(
            attrs,
            self.instance,
            "Collection Point must belong to exactly one hierarchy level.",
        )

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "state_id",
                    "district_id",
                    "corporation_id",
                    "municipality_id",
                    "town_panchayat_id",
                    "panchayat_union_id",
                    "panchayat_id",
                ],
            )(self, attrs)

        return attrs
