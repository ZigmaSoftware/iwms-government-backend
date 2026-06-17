from rest_framework import serializers
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.masters.department import Department
from app.models.masters.designation import Designation

from app.models.user_creations.staffcreation import Staffcreation, StaffPersonalDetails

from app.utils.password_encryption import encrypt_password, decrypt_password


class StaffApprovalActionSerializer(serializers.Serializer):
    rejected_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


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
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.filter(is_deleted=False),
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
    designation_name = serializers.CharField(
        source="designation_id.designation_name",
        read_only=True,
    )
    designation_group = serializers.CharField(
        source="designation_id.designation_group",
        read_only=True,
    )

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
            "doj",
            "department",
            "designation",
            "department_id",
            "designation_id",
            "department_name",
            "department_code",
            "designation_name",
            "designation_group",
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
            "approval_status",
            "login_enabled",
            "approved_by",
            "approved_at",
            "rejected_reason",
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
            "approval_status",
            "approved_by",
            "approved_at",
            "rejected_reason",
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

        staff = super().update(instance, validated_data)

        if personal_data:
            personal_instance, _ = StaffPersonalDetails.objects.get_or_create(
                staff=staff
            )
            if not getattr(personal_instance, "company_id", None):
                personal_instance.company_id = staff.company_id
            if not getattr(personal_instance, "project_id", None):
                personal_instance.project_id = staff.project_id
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
