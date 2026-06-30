from rest_framework import serializers

from app.models.customers.customercreation import CustomerCreation
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.validators.unique_name_validator import unique_name_validator
from app.utils.hierarchy import validate_single_hierarchy
from app.services.hierarchy_tree_service import get_path

from app.utils.password_encryption import encrypt_password, decrypt_password


class CustomerCreationSerializer(serializers.ModelSerializer):

    # ---- geography is now a single dynamic hierarchy node ----------------
    location_node_id = serializers.SlugRelatedField(
        source="location_node",
        queryset=HierarchyNode.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=True,
        allow_null=False,
    )
    location_node_name = serializers.CharField(source="location_node.name", read_only=True)
    location_name = serializers.CharField(source="location_node.name", read_only=True)
    location_level = serializers.CharField(source="location_node.level.name", read_only=True)
    location_path = serializers.SerializerMethodField(read_only=True)

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
            "location_node_id",
            "location_node_name",
            "location_name",
            "location_level",
            "location_path",
            "pincode",
            "latitude",
            "longitude",
            "sqft",
            "id_proof_type",
            "id_no",
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

    def validate(self, attrs):
        # attrs = unique_name_validator(
        #     Model=CustomerCreation,
        #     name_field="user_name",
        # )(self, attrs)

        instance = getattr(self, "instance", None)
        validate_single_hierarchy(
            attrs,
            instance,
            "Customer must be assigned to a hierarchy node.",
        )
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

    def get_location_path(self, obj):
        """Full ancestry of the customer's node, root -> node (for breadcrumbs)."""
        if not obj.location_node_id:
            return []
        return [
            {"unique_id": e["unique_id"], "name": e["name"], "level_name": e.get("level_name")}
            for e in get_path(obj.location_node_id)
        ]

    def get_waste_types(self, obj):
        return [
            {
                "unique_id": waste_type.unique_id,
                "waste_type_name": waste_type.waste_type_name,
            }
            for waste_type in obj.waste_types.filter(is_deleted=False).order_by("waste_type_name")
        ]
