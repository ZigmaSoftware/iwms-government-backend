from rest_framework import serializers
from django.db.models import Q

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.superadmin.role_management.userType import UserType


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accept related object via unique_id (slug) or numeric PK.
    Serialize always as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise serializers.ValidationError("Invalid reference value")


class StaffSerializer(serializers.ModelSerializer):

    # ---------- USER TYPE ----------
    user_type_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=UserType.objects.all(),
        required=True
    )

    user_type_name = serializers.CharField(
        source="user_type_id.name",
        read_only=True
    )

    # ---------- STAFF USER TYPE ----------
    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name", read_only=True
    )

    # ---------- CUSTOMER ----------
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_name = serializers.CharField(
        source="customer_id.customer_name", read_only=True
    )
    customer_contact = serializers.CharField(
        source="customer_id.customer_contact_no", read_only=True
    )

    # ---------- LOCATION ----------
    district_name = serializers.CharField(
        source="district_id.name", read_only=True
    )
    class Meta:
        model = Staffcreation
        fields = "__all__"

    # ==================================================
    # VALIDATION
    # ==================================================
    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        user_type = attrs.get("user_type_id") or (
            instance.user_type_id if instance else None
        )
        if not user_type:
            return attrs

        staffusertype_id = attrs.get("staffusertype_id") or (
            instance.staffusertype_id if instance else None
        )
        customer_id = attrs.get("customer_id") or (
            instance.customer_id if instance else None
        )

        # ---------- PHONE RESOLUTION ----------
        phone = None
        if hasattr(instance, "personal_details"):
            phone = instance.personal_details.contact_mobile
        elif customer_id:
            phone = customer_id.contact_no

        # ---------- DUPLICATE PHONE ----------
        if phone:
            # Check across Staffcreation and CustomerCreation
            staff_qs = Staffcreation.objects.filter(is_deleted=False)
            customer_qs = CustomerCreation.objects.filter(is_deleted=False)

            staff_exists = staff_qs.filter(
                Q(personal_details__contact_mobile=phone)
            ).exists()
            customer_exists = customer_qs.filter(
                Q(contact_no=phone)
            ).exists()

            if staff_exists or customer_exists:
                raise serializers.ValidationError({
                    "non_field_errors": (
                        "This contact number already exists. "
                        "A person cannot be duplicated as Staff or Customer."
                    )
                })

        # ---------- STRUCTURAL RULES ----------
        user_type_name = user_type.name.lower().strip()

        if user_type_name == "customer":
            if not customer_id:
                raise serializers.ValidationError({
                    "customer_id": "Required for Customer user type."
                })
            if staffusertype_id:
                raise serializers.ValidationError(
                    "Staff fields are not allowed for Customer."
                )

        elif user_type_name == "staff":
            if not staffusertype_id:
                raise serializers.ValidationError({
                    "staffusertype_id": "Required for Staff user type."
                })
            if customer_id:
                raise serializers.ValidationError(
                    "Customer fields are not allowed for Staff."
                )

        return attrs
