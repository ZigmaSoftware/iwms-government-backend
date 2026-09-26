import re

from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.wastetype import WasteType
from app.validators.unique_name_validator import unique_name_validator

from app.utils.password_encryption import encrypt_password, decrypt_password
from app.utils import ref_cache
from app.utils.hierarchy import (
    BARE_TO_ID_GEO_FIELDS,
    FLAT_GEO_FIELDS,
    normalize_flat_geo_attrs,
    validate_wards_for_flat_geo,
)

PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Z])(?=.*[a-z])(?=.*[^A-Za-z0-9]).{8,12}$")
PASSWORD_RULE_MESSAGE = (
    "Password must be 8-12 characters long and include at least one uppercase "
    "letter, one lowercase letter, and one special character."
)


class CustomerCreationSerializer(serializers.ModelSerializer):

    # ---- geography: state/district/area type/local body -------------------
    # Plain unique_id strings in (no DB relation) — CustomerCreation's own
    # columns are literally named "<field>_id" (matching Corporation/District/
    # etc.'s convention), so these need no `source=` override. Display names
    # resolved via explicit lookups, mirroring CorporationSerializer/DistrictSerializer.
    state_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    state_name = serializers.SerializerMethodField()

    district_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    district_name = serializers.SerializerMethodField()

    area_type_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    area_type_name = serializers.SerializerMethodField()

    corporation_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    corporation_name = serializers.SerializerMethodField()

    municipality_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    municipality_name = serializers.SerializerMethodField()

    town_panchayat_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    town_panchayat_name = serializers.SerializerMethodField()

    panchayat_union_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    panchayat_union_name = serializers.SerializerMethodField()

    panchayat_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    panchayat_name = serializers.SerializerMethodField()

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    def get_district_name(self, obj):
        return getattr(ref_cache.get(District, obj.district_id, "unique_id"), "name", None)

    def get_area_type_name(self, obj):
        return getattr(ref_cache.get(AreaType, obj.area_type_id, "unique_id"), "name", None)

    def get_corporation_name(self, obj):
        return getattr(ref_cache.get(Corporation, obj.corporation_id, "unique_id"), "corporation_name", None)

    def get_municipality_name(self, obj):
        return getattr(ref_cache.get(Municipality, obj.municipality_id, "unique_id"), "municipality_name", None)

    def get_town_panchayat_name(self, obj):
        return getattr(ref_cache.get(TownPanchayat, obj.town_panchayat_id, "unique_id"), "town_panchayat_name", None)

    def get_panchayat_union_name(self, obj):
        return getattr(ref_cache.get(PanchayatUnion, obj.panchayat_union_id, "unique_id"), "union_name", None)

    def get_panchayat_name(self, obj):
        return getattr(ref_cache.get(Panchayat, obj.panchayat_id, "unique_id"), "panchayat_name", None)

    # ward/property/sub-property/waste types are plain unique_id strings too
    # (no DB relation); existence is checked in the validate_* methods below.
    ward_id = serializers.CharField(required=True, allow_null=False, allow_blank=True)
    ward_name = serializers.SerializerMethodField()

    property_id = serializers.CharField()
    sub_property_id = serializers.CharField()
    waste_type_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    property_name = serializers.SerializerMethodField()
    sub_property_name = serializers.SerializerMethodField()
    waste_types = serializers.SerializerMethodField(read_only=True)

    def get_ward_name(self, obj):
        return getattr(obj.ward, "ward_name", None)

    def get_property_name(self, obj):
        return getattr(obj.property_ref, "property_name", None)

    def get_sub_property_name(self, obj):
        return getattr(obj.sub_property, "sub_property_name", None)

    apartment_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    block_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    flat_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    villa_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    member_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    family_members = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=True,
    )

    group_qr_id = serializers.CharField(read_only=True)
    is_bulkwaste_generator = serializers.BooleanField(required=False)
    qr_code = serializers.ImageField(read_only=True)

    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password_crt_date = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CustomerCreation
        fields = [
            "unique_id",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "apartment_name",
            "block_no",
            "flat_no",
            "villa_no",
            "industry_name",
            "industry_type",
            "group_qr_id",
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
            "ward_id",
            "ward_name",
            "pincode",
            "latitude",
            "longitude",
            "sqft",
            "water_consumption_lpd",
            "waste_collection_kg_per_day",
            "id_proof_type",
            "id_no",
            "member_count",
            "family_members",
            "property_id",
            "sub_property_id",
            "waste_type_ids",
            "waste_types",
            "username",
            "email",
            "password",
            "password_crt_date",
            "created_at",
            "is_deleted",
            "is_active",
            "property_name",
            "sub_property_name",
            "is_bulkwaste_generator",
            "qr_code",
        ]
        read_only_fields = ["unique_id", "password_crt_date", "created_at"]
        validators = []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get("view")
        if getattr(view, "action", None) == "list":
            data['password'] = ""
        else:
            data['password'] = decrypt_password(instance.password or "")
        return data

        # =============================
    # CREATE (ENCRYPT PASSWORD)
    # =============================
    def create(self, validated_data):
        password = validated_data.pop("password", None)

        instance = super().create(validated_data)

        if password:
            instance.password = encrypt_password(password)
            instance.save(update_fields=["password"])

        return instance

    # =============================
    # UPDATE (ENCRYPT PASSWORD)
    # =============================
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        instance = super().update(instance, validated_data)

        if password:
            instance.password = encrypt_password(password)
            instance.save(update_fields=["password"])

        return instance

    def validate_property_id(self, value):
        if not Property.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid property.")
        return value

    def validate_sub_property_id(self, value):
        if not SubProperty.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError("Invalid sub property.")
        return value

    def validate_waste_type_ids(self, value):
        value = list(dict.fromkeys(v for v in value if v))
        found = set(
            WasteType.objects.filter(
                unique_id__in=value, is_deleted=False
            ).values_list("unique_id", flat=True)
        )
        missing = [v for v in value if v not in found]
        if missing:
            raise serializers.ValidationError(
                f"Invalid waste type(s): {', '.join(missing)}"
            )
        return value

    def validate_password(self, value):
        if value and not PASSWORD_PATTERN.match(value):
            raise serializers.ValidationError(PASSWORD_RULE_MESSAGE)
        return value

    def validate_family_members(self, value):
        allowed_keys = {"member_name", "id_proof_type", "id_no"}
        valid_id_proof_types = {choice for choice, _ in CustomerCreation.IDProofType.choices}
        for member in value:
            if not isinstance(member, dict):
                raise serializers.ValidationError("Each family member must be an object.")
            extra_keys = set(member.keys()) - allowed_keys
            if extra_keys:
                raise serializers.ValidationError(
                    f"Unsupported family member field(s): {', '.join(sorted(extra_keys))}"
                )
            id_proof_type = member.get("id_proof_type")
            if id_proof_type and id_proof_type not in valid_id_proof_types:
                raise serializers.ValidationError(
                    f"Invalid id_proof_type '{id_proof_type}' for family member."
                )
        return value

    def validate(self, attrs):
        # attrs = unique_name_validator(
        #     Model=CustomerCreation,
        #     name_field="user_name",
        # )(self, attrs)

        instance = getattr(self, "instance", None)

        # The form sends "" for geo levels that don't apply; store NULL.
        for real in (*BARE_TO_ID_GEO_FIELDS.values(), "ward_id"):
            if attrs.get(real) == "":
                attrs[real] = None

        # `normalize_flat_geo_attrs`/`validate_wards_for_flat_geo` are shared
        # with still-FK-based callers (StaffTemplate/TripPlan) and operate in
        # terms of the bare geo-level names ("state", "corporation", ...).
        # CustomerCreation's own model fields are the "_id"-suffixed plain
        # CharFields, so translate both ways around these calls.
        bare_attrs = dict(attrs)
        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if real in bare_attrs:
                bare_attrs[bare] = bare_attrs.pop(real)

        geo_errors = normalize_flat_geo_attrs(
            bare_attrs, instance=instance, require_geo=True, as_strings=True
        )
        if geo_errors:
            raise serializers.ValidationError(geo_errors)

        ward_uid = (
            bare_attrs.get("ward_id")
            if "ward_id" in bare_attrs
            else getattr(instance, "ward_id", None)
        )
        if not ward_uid:
            geo_is_being_changed = any(
                field in bare_attrs for field in FLAT_GEO_FIELDS
            )
            if not instance or not self.partial or geo_is_being_changed:
                raise serializers.ValidationError({"ward_id": "Ward is required."})
        else:
            ward = Ward.objects.filter(unique_id=ward_uid, is_deleted=False).first()
            if not ward:
                raise serializers.ValidationError({"ward_id": "Invalid ward."})
            ward_error = validate_wards_for_flat_geo([ward], bare_attrs, instance)
            if ward_error:
                raise serializers.ValidationError({"ward_id": ward_error})

        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if bare in bare_attrs:
                attrs[real] = bare_attrs.pop(bare)
        attrs.update(bare_attrs)

        district = attrs.get("district_id") or getattr(instance, "district_id", None)
        if not district:
            raise serializers.ValidationError({"district_id": "Customer must be assigned to a district."})
        name = attrs.get("customer_name") or getattr(instance, "customer_name", None)
        mobile = attrs.get("contact_no") or getattr(instance, "contact_no", None)

        # if name and mobile:
        #     qs = CustomerCreation.objects.filter(
        #         customer_name__iexact=name,
        #         contact_no=mobile,
        #         is_deleted=False,
        #     )
        #     if instance:
        #         qs = qs.exclude(pk=instance.pk)
        #     if qs.exists():
        #         raise serializers.ValidationError(
        #             {"detail": "Customer with the same name and mobile already exists."}
        #         )

        sub_property_uid = attrs.get("sub_property_id") or getattr(instance, "sub_property_id", None)
        sub_property = (
            SubProperty.objects.filter(unique_id=sub_property_uid).first()
            if sub_property_uid
            else None
        )

        if sub_property:
            sub_name = (sub_property.sub_property_name or "").lower()

            def value(field_name):
                return attrs.get(field_name, getattr(instance, field_name, None))

            if "individual" in sub_name or "house" in sub_name:
                if not value("building_no") or not value("street") or not value("area"):
                    raise serializers.ValidationError("Building, street, and area required")
            elif "apartment" in sub_name:
                if not value("apartment_name") or not value("block_no"):
                    raise serializers.ValidationError("Apartment name and block required")
            elif "villa" in sub_name:
                if not value("building_no"):
                    raise serializers.ValidationError("Building number required for villa")
            elif "industry" in sub_name:
                if not value("industry_name"):
                    raise serializers.ValidationError("Industry name required")

        return attrs

    def get_waste_types(self, obj):
        return [
            {
                "unique_id": waste_type.unique_id,
                "waste_type_name": waste_type.waste_type_name,
            }
            for waste_type in obj.waste_types.filter(is_deleted=False).order_by("waste_type_name")
        ]
