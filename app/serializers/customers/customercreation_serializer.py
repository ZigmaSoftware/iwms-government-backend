from rest_framework import serializers

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.validators.unique_name_validator import unique_name_validator

from django.contrib.auth.hashers import make_password


class CustomerCreationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    company_id = serializers.SlugRelatedField(
        # source="company_id",
        queryset=Company.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
        )

    project_id = serializers.SlugRelatedField(
        # source="project_id",
        queryset=Project.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    ward_id = serializers.SlugRelatedField(
        source="ward",
        queryset=Ward.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    zone_id = serializers.SlugRelatedField(
        source="zone",
        queryset=Zone.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    city_id = serializers.SlugRelatedField (
        source="city",
        queryset=City.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    district_id = serializers.SlugRelatedField(
        source="district",
        queryset=District.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    state_id = serializers.SlugRelatedField(
        source="state",
        queryset=State.objects.all(),
        slug_field="unique_id",
    )
    country_id = serializers.SlugRelatedField(
        source="country",
        queryset=Country.objects.all(),
        slug_field="unique_id",
    )
    panchayat_id = serializers.SlugRelatedField(
        # source="panchayat_id",
        queryset=Panchayat.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
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
    panchayat_id = serializers.SlugRelatedField(
        # source="panchayat_id",
        queryset=Panchayat.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    property_name = serializers.CharField(source="property_ref.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

    apartment_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    block_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    flat_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    villa_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    group_qr_id = serializers.CharField(read_only=True)
    is_bulkwaste_generator = serializers.BooleanField(read_only=True)
    qr_code = serializers.ImageField(read_only=True)

    password = serializers.CharField(write_only=True, required=False)
    password_crt_date = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CustomerCreation
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
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
            "ward_id",
            "zone_id",
            "city_id",
            "district_id",
            "state_id",
            "country_id",
            "panchayat_id",
            "pincode",
            "latitude",
            "longitude",
            "sqft",
            "id_proof_type",
            "id_no",
            "property_id",
            "sub_property_id",
            "username",
            "email",
            "password",
            "password_crt_date",
            "created_at",
            "is_deleted",
            "is_active",
            "ward_name",
            "zone_name",
            "panchayat_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "property_name",
            "sub_property_name",
            "is_bulkwaste_generator",
            "qr_code",
        ]
        read_only_fields = ["unique_id", "password_crt_date", "created_at"]
        validators = []


        # =============================
    # CREATE (HASH PASSWORD)
    # =============================
    def create(self, validated_data):
        password = validated_data.pop("password", None)

        instance = super().create(validated_data)

        if password:
            instance.password = make_password(password)
            instance.save(update_fields=["password"])

        return instance

    # =============================
    # UPDATE (HASH PASSWORD)
    # =============================
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        instance = super().update(instance, validated_data)

        if password:
            instance.password = make_password(password)
            instance.save(update_fields=["password"])

        return instance

    def validate(self, attrs):
        # attrs = unique_name_validator(
        #     Model=CustomerCreation,
        #     name_field="user_name",
        # )(self, attrs)

        instance = getattr(self, "instance", None)
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
