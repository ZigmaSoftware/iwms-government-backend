from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from app.models.masters.waste_masters.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.waste_masters.wastetype import WasteType
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import BARE_TO_ID_GEO_FIELDS, normalize_flat_geo_attrs, validate_wards_for_flat_geo


class CollectionPointBinInputSerializer(serializers.Serializer):
    unique_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wastetype_id = serializers.CharField()
    bin_name = serializers.CharField()
    bin_capacity = serializers.IntegerField()
    bin_type = serializers.ChoiceField(choices=BinType.choices)
    ward_id = serializers.SlugRelatedField(
        queryset=Ward.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=True,
    )
    is_active = serializers.BooleanField(default=True)


class CollectionPointSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    country_id = serializers.CharField(required=False, allow_null=True)
    country_name = serializers.SerializerMethodField()
    state_id = serializers.CharField(required=False, allow_null=True)
    state_name = serializers.SerializerMethodField()
    district_id = serializers.CharField(required=True)
    district_name = serializers.SerializerMethodField()
    area_type_id = serializers.CharField(required=False, allow_null=True)
    area_type_name = serializers.SerializerMethodField()
    corporation_id = serializers.CharField(required=False, allow_null=True)
    corporation_name = serializers.SerializerMethodField()
    municipality_id = serializers.CharField(required=False, allow_null=True)
    municipality_name = serializers.SerializerMethodField()
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_name = serializers.SerializerMethodField()
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_name = serializers.SerializerMethodField()
    panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_name = serializers.SerializerMethodField()

    def get_country_name(self, obj):
        return Country.objects.filter(unique_id=obj.country_id).values_list("name", flat=True).first()

    def get_state_name(self, obj):
        return State.objects.filter(unique_id=obj.state_id).values_list("name", flat=True).first()

    def get_district_name(self, obj):
        return District.objects.filter(unique_id=obj.district_id).values_list("name", flat=True).first()

    def get_area_type_name(self, obj):
        return AreaType.objects.filter(unique_id=obj.area_type_id).values_list("name", flat=True).first()

    def get_corporation_name(self, obj):
        return Corporation.objects.filter(unique_id=obj.corporation_id).values_list("corporation_name", flat=True).first()

    def get_municipality_name(self, obj):
        return Municipality.objects.filter(unique_id=obj.municipality_id).values_list("municipality_name", flat=True).first()

    def get_town_panchayat_name(self, obj):
        return TownPanchayat.objects.filter(unique_id=obj.town_panchayat_id).values_list("town_panchayat_name", flat=True).first()

    def get_panchayat_union_name(self, obj):
        return PanchayatUnion.objects.filter(unique_id=obj.panchayat_union_id).values_list("union_name", flat=True).first()

    def get_panchayat_name(self, obj):
        return Panchayat.objects.filter(unique_id=obj.panchayat_id).values_list("panchayat_name", flat=True).first()

    bins = CollectionPointBinInputSerializer(many=True, write_only=True, required=False)
    bins_detail = serializers.SerializerMethodField()
    ward_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        many=True,
        required=False,
        source="wards",
        write_only=True,
    )
    wards_detail = serializers.SerializerMethodField()

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "country_id",
            "country_name",
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
            "ward_ids",
            "wards_detail",
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
            "ward_id": bin_obj.ward_id,
            "ward_name": getattr(bin_obj.ward, "ward_name", None),
            "bin_qr": bin_obj.bin_qr.url if bin_obj.bin_qr else None,
            "wastetype_id": bin_obj.wastetype_id_id,
            "wastetype_name": getattr(bin_obj.wastetype_id, "waste_type_name", None),
            "is_active": bin_obj.is_active,
        } for bin_obj in bins]

    def get_wards_detail(self, obj):
        return [
            {"unique_id": ward.unique_id, "ward_name": ward.ward_name}
            for ward in obj.wards.all()
        ]

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
                existing.ward = bin_data["ward_id"]
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
                    ward=bin_data["ward_id"],
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

        # `normalize_flat_geo_attrs` works in terms of the bare geo-level
        # names ("state", "corporation", ...) both for reading `attrs`/
        # `instance` and for the keys it writes back. Collection_point's own
        # model fields are the "_id"-suffixed plain CharFields (post
        # conversion), so translate both ways around the call — same
        # convention as WardSerializer.
        bare_attrs = dict(attrs)
        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if real in bare_attrs:
                bare_attrs[bare] = bare_attrs.pop(real)

        geo_errors = normalize_flat_geo_attrs(
            bare_attrs, instance=instance, require_geo=True, as_strings=True
        )
        if geo_errors:
            raise serializers.ValidationError(geo_errors)

        wards = attrs.get("wards")
        effective_wards = list(wards) if wards is not None else (
            list(instance.wards.all()) if instance else []
        )
        if not effective_wards:
            hierarchy_is_being_changed = any(
                field in attrs
                for field in (
                    "state_id", "district_id", "area_type_id", "corporation_id",
                    "municipality_id", "town_panchayat_id", "panchayat_union_id",
                    "panchayat_id",
                )
            )
            legacy_partial_update = (
                instance
                and self.partial
                and "wards" not in attrs
                and "bins" not in attrs
                and not hierarchy_is_being_changed
            )
            if not legacy_partial_update:
                raise serializers.ValidationError(
                    {"ward_ids": "Select at least one ward."}
                )
        else:
            ward_error = validate_wards_for_flat_geo(effective_wards, bare_attrs, instance)
            if ward_error:
                raise serializers.ValidationError({"ward_ids": ward_error})

        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if bare in bare_attrs:
                attrs[real] = bare_attrs.pop(bare)
        attrs.update(bare_attrs)

        submitted_bins = attrs.get("bins")
        if submitted_bins is not None:
            for index, bin_data in enumerate(submitted_bins):
                if bin_data["ward_id"] not in effective_wards:
                    raise serializers.ValidationError(
                        {"bins": {index: {"ward_id": "Bin ward must be selected for this collection point."}}}
                    )
        elif instance and "wards" in attrs:
            allowed_ward_ids = {ward.pk for ward in effective_wards}
            invalid_existing_bin = instance.bin.filter(
                Q(ward__isnull=True) | ~Q(ward_id__in=allowed_ward_ids),
                is_deleted=False,
            ).exists()
            if invalid_existing_bin:
                raise serializers.ValidationError(
                    {
                        "ward_ids": (
                            "A ward assigned to an existing bin cannot be removed "
                            "from the collection point."
                        )
                    }
                )

        state_id = attrs.get("state_id") if "state_id" in attrs else getattr(instance, "state_id", None)
        country_id = attrs.get("country_id") if "country_id" in attrs else getattr(instance, "country_id", None)
        district_id = attrs.get("district_id") if "district_id" in attrs else getattr(instance, "district_id", None)

        if state_id:
            state = State.objects.filter(unique_id=state_id).first()
            state_country_id = state.country_id if state else None
            if country_id and state_country_id and country_id != state_country_id:
                raise serializers.ValidationError(
                    {"country_id": "Country must match the selected state."}
                )
            attrs["country_id"] = state_country_id

        if not district_id:
            raise serializers.ValidationError({"district_id": "Collection Point must be assigned to a district."})

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "country_id",
                    "district_id",
                    "corporation_id",
                    "municipality_id",
                    "town_panchayat_id",
                    "panchayat_union_id",
                    "panchayat_id",
                ],
            )(self, attrs)

        return attrs
