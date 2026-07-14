from rest_framework import serializers
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.masters.department import Department
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat

from app.models.user_creations.staffcreation import Staffcreation, StaffPersonalDetails

from app.utils.password_encryption import encrypt_password, decrypt_password


class StaffcreationSerializer(serializers.ModelSerializer):
    # --------------------------------------------------
    # Core identifiers
    # --------------------------------------------------
    unique_id = serializers.CharField(source="staff_unique_id",read_only=True)
    emp_id = serializers.CharField(read_only=True)
    staffusertype_id = serializers.PrimaryKeyRelatedField(
    queryset=StaffUserType.objects.all(),
    required=False,
    allow_null=True
)
    password = serializers.CharField(
    required=False,
    allow_blank=True,
    allow_null=True,
)

    staffusertype_name = serializers.CharField(
    source="staffusertype_id.name",
    read_only=True
)

    contractorusertype_id = serializers.PrimaryKeyRelatedField(
        queryset=ContractorUserType.objects.all(),
        required=False,
        allow_null=True,
    )
    contractorusertype_name = serializers.CharField(
        source="contractorusertype_id.name",
        read_only=True,
    )
    governmentusertype_id = serializers.PrimaryKeyRelatedField(
        queryset=GovernmentStaffUserType.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    governmentusertype_name = serializers.CharField(
        source="governmentusertype_id.name",
        read_only=True,
    )
    governmentusertype_level = serializers.CharField(
        source="governmentusertype_id.level",
        read_only=True,
    )
    state_id = serializers.SlugRelatedField(
        source="state",
        queryset=State.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    state_name = serializers.CharField(source="state.name", read_only=True)

    district_id = serializers.SlugRelatedField(
        source="district",
        queryset=District.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    district_name = serializers.CharField(source="district.name", read_only=True)

    area_type_id = serializers.SlugRelatedField(
        source="area_type",
        queryset=AreaType.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)

    corporation_id = serializers.SlugRelatedField(
        source="corporation",
        queryset=Corporation.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    corporation_name = serializers.CharField(source="corporation.name", read_only=True)

    municipality_id = serializers.SlugRelatedField(
        source="municipality",
        queryset=Municipality.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    municipality_name = serializers.CharField(source="municipality.name", read_only=True)

    town_panchayat_id = serializers.SlugRelatedField(
        source="town_panchayat",
        queryset=TownPanchayat.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    town_panchayat_name = serializers.CharField(source="town_panchayat.name", read_only=True)

    panchayat_union_id = serializers.SlugRelatedField(
        source="panchayat_union",
        queryset=PanchayatUnion.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    panchayat_union_name = serializers.CharField(source="panchayat_union.name", read_only=True)

    panchayat_id = serializers.SlugRelatedField(
        source="panchayat",
        queryset=Panchayat.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    panchayat_name = serializers.CharField(source="panchayat.name", read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    department_name = serializers.CharField(
        source="department_id.department_name",
        read_only=True,
    )
    department_code = serializers.CharField(
        source="department_id.department_code",
        read_only=True,
    )
    # Designation is captured as free text (`designation`), not an FK master —
    # government designations vary too widely across states/districts to
    # enumerate. The former FK (`designation_id`) is no longer exposed.

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
    
    user_type_id = serializers.CharField(
    source="staffusertype_id.usertype_id.unique_id",read_only=True)

    

    # --------------------------------------------------
    # Internal mapping for personal table
    # --------------------------------------------------
    personal_field_names = [
        "marital_status",
        "dob",
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
            "password",
            "qr_code",

            # Office details
            "employee_name",
            "staff_config_name",
            "doj",
            "department",
            "designation",
            "department_id",
            "department_name",
            "department_code",
            "staff_head_id",
            "grade",
            "site_name",
            "staff_head",
            "employee_known",
            "photo",

            #  Driving licence
            "driving_licence_no",
            "driving_licence_expiry_date",
            "driving_licence_file",

            "active_status",
            "salary_type",

            # Personal details (flattened)
            "marital_status",
            "dob",
            "blood_group",
            "gender",
            "physically_challenged",
            "present_address",
            "permanent_address",
            "contact_mobile",
            "contact_email",
            "user_type_id",
            "staffusertype_id",
            "staffusertype_name",
            "contractorusertype_id",
            "contractorusertype_name",

            # Government user type
            "governmentusertype_id",
            "governmentusertype_name",
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

        staffusertype = validated_data.get("staffusertype_id")
        if staffusertype and staffusertype.usertype_id:
            validated_data["user_type_id"] = staffusertype.usertype_id

        contractorusertype = validated_data.get("contractorusertype_id")
        if contractorusertype and contractorusertype.usertype_id:
            validated_data["user_type_id"] = contractorusertype.usertype_id

        governmentusertype = validated_data.get("governmentusertype_id")
        if governmentusertype and governmentusertype.usertype_id:
            validated_data["user_type_id"] = governmentusertype.usertype_id

        staff = Staffcreation.objects.create(**validated_data)

        StaffPersonalDetails.objects.create(
            staff=staff,
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

        staffusertype = validated_data.get("staffusertype_id")
        if staffusertype and staffusertype.usertype_id:
            validated_data["user_type_id"] = staffusertype.usertype_id

        contractorusertype = validated_data.get("contractorusertype_id")
        if contractorusertype and contractorusertype.usertype_id:
            validated_data["user_type_id"] = contractorusertype.usertype_id

        governmentusertype = validated_data.get("governmentusertype_id")
        if governmentusertype and governmentusertype.usertype_id:
            validated_data["user_type_id"] = governmentusertype.usertype_id

        staff = super().update(instance, validated_data)

        if personal_data:
            personal_instance, _ = StaffPersonalDetails.objects.get_or_create(
                staff=staff
            )
            for attr, value in personal_data.items():
                setattr(personal_instance, attr, value)

            personal_instance.staff_unique_id = staff.staff_unique_id
            personal_instance.save()
        else:
            if hasattr(staff, "personal_details"):
                personal_details = staff.personal_details
                if personal_details.staff_unique_id != staff.staff_unique_id:
                    personal_details.staff_unique_id = staff.staff_unique_id
                    personal_details.save()

        return staff
