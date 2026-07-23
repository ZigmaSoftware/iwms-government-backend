from django.db import transaction
from rest_framework import serializers

from app.models.assets.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.assets.wastetype import WasteType
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class CollectionPointBinInputSerializer(serializers.Serializer):
    unique_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wastetype_id = serializers.CharField()
    bin_name = serializers.CharField()
    bin_capacity = serializers.IntegerField()
    bin_type = serializers.ChoiceField(choices=BinType.choices)
    is_active = serializers.BooleanField(default=True)


class CollectionPointSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), required=False, allow_null=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), required=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    area_type_id = UniqueIdOrPkField(source="area_type", slug_field="unique_id", queryset=AreaType.objects.filter(is_deleted=False), required=False, allow_null=True)
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)
    corporation_id = UniqueIdOrPkField(source="corporation", slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), required=False, allow_null=True)
    corporation_name = serializers.CharField(source="corporation.corporation_name", read_only=True)
    municipality_id = UniqueIdOrPkField(source="municipality", slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), required=False, allow_null=True)
    municipality_name = serializers.CharField(source="municipality.municipality_name", read_only=True)
    town_panchayat_id = UniqueIdOrPkField(source="town_panchayat", slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), required=False, allow_null=True)
    town_panchayat_name = serializers.CharField(source="town_panchayat.town_panchayat_name", read_only=True)
    panchayat_union_id = UniqueIdOrPkField(source="panchayat_union", slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), required=False, allow_null=True)
    panchayat_union_name = serializers.CharField(source="panchayat_union.union_name", read_only=True)
    panchayat_id = UniqueIdOrPkField(source="panchayat", slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), required=False, allow_null=True)
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True)

    bins = CollectionPointBinInputSerializer(many=True, write_only=True, required=False)
    bins_detail = serializers.SerializerMethodField()

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
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
            "collection_type",
            "latitude",
            "longitude",
            "coordinates",
            "bins",
            "bins_detail",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_bins_detail(self, obj):
        bins = obj.bin.filter(is_deleted=False)
        return [{
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
            "bin_qr": bin_obj.bin_qr.url if bin_obj.bin_qr else None,
            "wastetype_id": bin_obj.wastetype_id_id,
            "wastetype_name": getattr(bin_obj.wastetype_id, "waste_type_name", None),
            "is_active": bin_obj.is_active,
        } for bin_obj in bins]

    def _sync_bins(self, collection_point, bins):
        if bins is None:
            return
        submitted_ids = {bin_data["unique_id"] for bin_data in bins if bin_data.get("unique_id")}
        Bins.objects.filter(collection_point_id=collection_point).exclude(unique_id__in=submitted_ids).update(
            is_active=False, is_deleted=True,
        )
        for bin_data in bins:
            waste_type = WasteType.objects.get(unique_id=bin_data["wastetype_id"])
            unique_id = bin_data.get("unique_id")
            existing = (
                Bins.objects.filter(unique_id=unique_id, collection_point_id=collection_point).first()
                if unique_id else None
            )
            if existing:
                existing.wastetype_id = waste_type
                existing.bin_name = bin_data["bin_name"]
                existing.bin_capacity = bin_data["bin_capacity"]
                existing.bin_type = bin_data["bin_type"]
                existing.is_active = bin_data.get("is_active", True)
                existing.is_deleted = False
                existing.save()
            else:
                Bins.objects.create(
                    collection_point_id=collection_point,
                    wastetype_id=waste_type,
                    bin_name=bin_data["bin_name"],
                    bin_capacity=bin_data["bin_capacity"],
                    bin_type=bin_data["bin_type"],
                    bin_image="default.png",
                    is_active=bin_data.get("is_active", True),
                )

    @transaction.atomic
    def create(self, validated_data):
        bins = validated_data.pop("bins", None)
        collection_point = super().create(validated_data)
        self._sync_bins(collection_point, bins)
        return collection_point

    @transaction.atomic
    def update(self, instance, validated_data):
        bins = validated_data.pop("bins", None)
        collection_point = super().update(instance, validated_data)
        self._sync_bins(collection_point, bins)
        return collection_point

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        district = attrs.get("district") or getattr(instance, "district", None)
        if not district:
            raise serializers.ValidationError({"district_id": "Collection Point must be assigned to a district."})

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "district",
                    "corporation",
                    "municipality",
                    "town_panchayat",
                    "panchayat_union",
                    "panchayat",
                ],
            )(self, attrs)

        return attrs
