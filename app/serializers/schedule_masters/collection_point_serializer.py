from rest_framework import serializers
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.validators.unique_name_validator import unique_name_validator


class CollectionPointSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only = True)
    city_name = serializers.CharField(source="city_id.name", read_only = True)
    district_name = serializers.CharField(source="district_id.name", read_only = True)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only = True)
    ward_name = serializers.CharField(
        source="ward_id.ward_name",
        read_only=True
    )
    zone_id = serializers.CharField(source="ward_id.zone_id.unique_id", read_only=True)  
    zone_name = serializers.CharField(source="ward_id.zone_id.zone_name", read_only=True)  

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",
            "panchayat_id",
            "panchayat_name",
            "zone_id",
            "zone_name",
            "ward_id",
            "ward_name",
            "cp_name",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted"
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]


    def validate(self, attrs):

        panchayat = attrs.get("panchayat_id") or getattr(self.instance, "panchayat_id", None)
        ward = attrs.get("ward_id") or getattr(self.instance, "ward_id", None)

        #  Must belong to one
        if not panchayat and not ward:
            raise serializers.ValidationError(
                "Collection Point must belong to Ward or Panchayat."
            )

        #  Cannot belong to both
        if panchayat and ward:
            raise serializers.ValidationError(
                "Collection Point cannot belong to both Ward and Panchayat."
            )

        # Unique validation scope
        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "state_id",
                    "panchayat_id",
                    "ward_id"
                ]
            )(self, attrs)

        return attrs