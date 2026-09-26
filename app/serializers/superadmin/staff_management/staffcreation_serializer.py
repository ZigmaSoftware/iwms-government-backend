import re

from rest_framework import serializers
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.common_masters.state import State

from app.models.superadmin.staff_management.staffcreation import Staffcreation, StaffPersonalDetails

from app.utils.password_encryption import encrypt_password, decrypt_password
from app.utils.file_validators import validate_pdf_upload
from app.utils import ref_cache


class StaffcreationSerializer(serializers.ModelSerializer):
    # --------------------------------------------------
    # Core identifiers
    # --------------------------------------------------
    unique_id = serializers.CharField(source="staff_unique_id", read_only=True)
    emp_id = serializers.CharField(read_only=True)
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffusertype_name = serializers.SerializerMethodField()
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    contractorusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorusertype_name = serializers.SerializerMethodField()
    governmentusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    governmentusertype_name = serializers.SerializerMethodField()
    # Staff-named response aliases. Keep the legacy ``*usertype*`` fields
    # during the API transition so existing mobile/web clients remain valid.
    government_staff_type_name = serializers.SerializerMethodField()
    governmentusertype_level = serializers.SerializerMethodField()
    # Geo hierarchy: plain unique_id strings in, display names out.
    # Staffcreation's own columns are literally named "<field>_id" (CharField,
    # no DB relation) — same convention as Ward/Corporation/District/etc —
    # so these input fields need no `source=` override.
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

    def get_staffusertype_name(self, obj):
        return getattr(obj.staffusertype, "name", None)

    def get_contractorusertype_name(self, obj):
        return getattr(obj.contractorusertype, "name", None)

    def get_governmentusertype_name(self, obj):
        return getattr(obj.governmentusertype, "name", None)

    def get_government_staff_type_name(self, obj):
        return getattr(obj.governmentusertype, "name", None)

    def get_governmentusertype_level(self, obj):
        return getattr(obj.governmentusertype, "level", None)

    def get_department_name(self, obj):
        return getattr(obj.department_ref, "department_name", None)

    def get_designation_name(self, obj):
        return getattr(obj.designation_ref, "designation_name", None)

    department_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    designation_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    department_name = serializers.SerializerMethodField()
    designation_name = serializers.SerializerMethodField()
    # --------------------------------------------------
    #  Office-level: Driving licence
    # --------------------------------------------------
    driving_licence_no = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    driving_licence_file = serializers.FileField(
        required=False,
        allow_null=True,
        validators=[validate_pdf_upload],
    )
    driving_experience_years = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    # --------------------------------------------------
    # Personal details (flattened from StaffPersonalDetails)
    # --------------------------------------------------
    marital_status = serializers.CharField(
        source="personal_details.marital_status",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    dob = serializers.DateField(
        source="personal_details.dob",
        required=False,
        allow_null=True,
    )
    age = serializers.IntegerField(
        source="personal_details.age",
        required=False,
        allow_null=True,
        min_value=18,
        max_value=120,
    )
    blood_group = serializers.CharField(
        source="personal_details.blood_group",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    gender = serializers.CharField(
        source="personal_details.gender",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    physically_challenged = serializers.CharField(
        source="personal_details.physically_challenged",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    present_address = serializers.JSONField(
        source="personal_details.present_address",
        required=False,
        allow_null=True,
    )
    permanent_address = serializers.JSONField(
        source="personal_details.permanent_address",
        required=False,
        allow_null=True,
    )
    contact_mobile = serializers.CharField(
        source="personal_details.contact_mobile",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    contact_email = serializers.EmailField(
        source="personal_details.contact_email",
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    username = serializers.CharField(
    required=False,
    allow_blank=True,
    allow_null=True
)

    def validate_username(self, value):
        if not value:
            return value
        qs = Staffcreation.objects.filter(username=value, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A staff member with this username already exists.")
        return value

    def _validate_address_pincode(self, value):
        if not value:
            return value
        pincode = value.get("pincode") if isinstance(value, dict) else None
        if pincode not in (None, "") and not re.match(r"^\d{6}$", str(pincode)):
            raise serializers.ValidationError({"pincode": "Enter a valid 6-digit pincode."})
        return value

    def validate_present_address(self, value):
        return self._validate_address_pincode(value)

    def validate_permanent_address(self, value):
        return self._validate_address_pincode(value)

    user_type_id = serializers.CharField(
    source="staffusertype.usertype_id",read_only=True)

    # Readable name of the staff's own user type (e.g. "government").
    user_type_name = serializers.CharField(
        source="user_type_id.name",
        read_only=True,
    )
    staff_type_name = serializers.CharField(
        source="user_type_id.name",
        read_only=True,
    )

    

    # --------------------------------------------------
    # Internal mapping for personal table
    # --------------------------------------------------
    personal_field_names = [
        "marital_status",
        "dob",
        "age",
        "blood_group",
        "gender",
        "physically_challenged",
        "present_address",
        "permanent_address",
        "contact_mobile",
        "contact_email",
    ]

    class Meta:
        model = Staffcreation
        fields = [
            "unique_id",
            "emp_id",
            "username",
            "office_email",
            "password",
            # Which mobile app this staff member lands in. Explicit rather
            # than guessed from the role name (see app_feature_grants).
            #
            # Was missing from this list, so the Staff Creation form's
            # "Mobile App" dropdown was write-only-in-appearance: DRF drops
            # unknown keys silently, so the value the form posted was
            # discarded, and since it was never serialized back out either,
            # the edit form re-opened showing "No app access" for everyone
            # regardless of what was actually stored. Granting access is
            # still a separate thing — see StaffAccessConfiguration.
            "app_module",
            "qr_code",

            # Office details
            "employee_name",
            "staff_config_name",
            "doj",
            "staff_head_id",
            "staff_head",
            "photo",
            "attendance_reg_image",

            #  Driving licence
            "driving_licence_no",
            "driving_licence_expiry_date",
            "driving_licence_file",
            "driving_experience_years",

            "active_status",

            # Department and Designation (plain unique_id strings)
            "department_id",
            "designation_id",
            "department_name",
            "designation_name",

            # Personal details (flattened)
            "marital_status",
            "dob",
            "age",
            "blood_group",
            "gender",
            "physically_challenged",
            "present_address",
            "permanent_address",
            "contact_mobile",
            "contact_email",
            "user_type_id",
            "user_type_name",
            "staff_type_name",
            "staffusertype_id",
            "staffusertype_name",
            "contractorusertype_id",
            "contractorusertype_name",

            # Government user type
            "governmentusertype_id",
            "governmentusertype_name",
            "government_staff_type_name",
            "governmentusertype_level",

            # Geographic hierarchy for government staff
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

            "login_enabled",
            "failed_login_attempts",
            "last_login_at",
            "last_login_ip",

            "password_crt_date",
            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "qr_code",
            "failed_login_attempts",
            "last_login_at",
            "last_login_ip",
            "password_crt_date",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['password'] = decrypt_password(instance.password or "")
        return data

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _pop_personal_data(self, validated_data):
        """
        Extract personal detail payload for StaffPersonalDetails
        """
        personal_data = validated_data.pop("personal_details", {})
        return {
            field: personal_data[field]
            for field in self.personal_field_names
            if field in personal_data
        }

    # --------------------------------------------------
    # Create
    # --------------------------------------------------
    def create(self, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        password = validated_data.get("password")
        if password:
            validated_data["password"] = encrypt_password(password)


        validated_data["is_active"] = True

        staffusertype_id = validated_data.get("staffusertype_id")
        if staffusertype_id:
            from app.models.superadmin.role_management.staffUserType import StaffUserType
            staffusertype = ref_cache.get(StaffUserType, staffusertype_id)
            if staffusertype and staffusertype.usertype_id:
                validated_data["user_type_id"] = staffusertype.usertype_id

        contractorusertype_id = validated_data.get("contractorusertype_id")
        if contractorusertype_id:
            from app.models.superadmin.role_management.contractorUserType import ContractorUserType
            contractorusertype = ref_cache.get(ContractorUserType, contractorusertype_id)
            if contractorusertype and contractorusertype.usertype_id:
                validated_data["user_type_id"] = contractorusertype.usertype_id

        governmentusertype_id = validated_data.get("governmentusertype_id")
        if governmentusertype_id:
            from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
            governmentusertype = ref_cache.get(GovernmentStaffUserType, governmentusertype_id)
            if governmentusertype and governmentusertype.usertype_id:
                validated_data["user_type_id"] = governmentusertype.usertype_id

        staff = Staffcreation.objects.create(**validated_data)

        StaffPersonalDetails.objects.create(
            staff_id=staff.staff_unique_id,
            staff_unique_id=staff.staff_unique_id,
            **personal_data,
        )

        return staff

    # --------------------------------------------------
    # Update
    # --------------------------------------------------
    def update(self, instance, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        password = validated_data.get("password")
        if password:
            validated_data["password"] = encrypt_password(password)

        staffusertype_id = validated_data.get("staffusertype_id")
        if staffusertype_id:
            from app.models.superadmin.role_management.staffUserType import StaffUserType
            staffusertype = ref_cache.get(StaffUserType, staffusertype_id)
            if staffusertype and staffusertype.usertype_id:
                validated_data["user_type_id"] = staffusertype.usertype_id

        contractorusertype_id = validated_data.get("contractorusertype_id")
        if contractorusertype_id:
            from app.models.superadmin.role_management.contractorUserType import ContractorUserType
            contractorusertype = ref_cache.get(ContractorUserType, contractorusertype_id)
            if contractorusertype and contractorusertype.usertype_id:
                validated_data["user_type_id"] = contractorusertype.usertype_id

        governmentusertype_id = validated_data.get("governmentusertype_id")
        if governmentusertype_id:
            from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
            governmentusertype = ref_cache.get(GovernmentStaffUserType, governmentusertype_id)
            if governmentusertype and governmentusertype.usertype_id:
                validated_data["user_type_id"] = governmentusertype.usertype_id

        staff = super().update(instance, validated_data)

        if personal_data:
            personal_instance, _ = StaffPersonalDetails.objects.get_or_create(
                staff_id=staff.staff_unique_id
            )
            for attr, value in personal_data.items():
                setattr(personal_instance, attr, value)

            personal_instance.staff_unique_id = staff.staff_unique_id
            personal_instance.save()
        else:
            personal_details = staff.personal_details
            if personal_details is not None:
                if personal_details.staff_unique_id != staff.staff_unique_id:
                    personal_details.staff_unique_id = staff.staff_unique_id
                    personal_details.save()

        return staff
