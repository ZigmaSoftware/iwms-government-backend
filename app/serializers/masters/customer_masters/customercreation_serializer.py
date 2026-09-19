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
    state_id = serializers.CharField(required=False, allow_null=True)
    state_name = serializers.SerializerMethodField()

    district_id = serializers.CharField(required=False, allow_null=True)
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

    ward_id = serializers.SlugRelatedField(
        source="ward",
        queryset=Ward.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=True,
        allow_null=False,
    )
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)

    property_id = serializers.SlugRelatedField(
        source="property_ref",
        queryset=Property.objects.all(),
        slug_field="unique_id",
    )
    sub_property_id = serializers.SlugRelatedField(
        source="sub_property",
        queryset=SubProperty.objects.all(),
        slug_field="unique_id",
    )
    waste_type_ids = serializers.SlugRelatedField(
        source="waste_types",
        queryset=WasteType.objects.filter(is_deleted=False),
        slug_field="unique_id",
        many=True,
        required=False,
    )
    property_name = serializers.CharField(source="property_ref.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)
    waste_types = serializers.SerializerMethodField(read_only=True)

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

        ward = bare_attrs.get("ward") or getattr(instance, "ward", None)
        if not ward:
            geo_is_being_changed = any(
                field in bare_attrs for field in FLAT_GEO_FIELDS
            )
            if not instance or not self.partial or geo_is_being_changed:
                raise serializers.ValidationError({"ward_id": "Ward is required."})
        else:
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

        sub_property = attrs.get("sub_property") or getattr(instance, "sub_property", None)

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
            for waste_type in obj.waste_types.all()
        ]
