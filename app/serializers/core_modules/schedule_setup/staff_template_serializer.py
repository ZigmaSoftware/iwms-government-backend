from rest_framework import serializers
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import normalize_flat_geo_attrs


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(serializers.ModelSerializer):

    driver_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    operator_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )




    approved_by = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True
    )

    # ---- Geo hierarchy (write via *_id, read via nested objects) ----
    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    area_type_id = UniqueIdOrPkField(source="area_type", slug_field="unique_id", queryset=AreaType.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    corporation_id = UniqueIdOrPkField(source="corporation", slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    municipality_id = UniqueIdOrPkField(source="municipality", slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    town_panchayat_id = UniqueIdOrPkField(source="town_panchayat", slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_union_id = UniqueIdOrPkField(source="panchayat_union", slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_id = UniqueIdOrPkField(source="panchayat", slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)

    state = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    area_type = serializers.SerializerMethodField(read_only=True)
    corporation = serializers.SerializerMethodField(read_only=True)
    municipality = serializers.SerializerMethodField(read_only=True)
    town_panchayat = serializers.SerializerMethodField(read_only=True)
    panchayat_union = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)

    driver_name = serializers.CharField(source="driver_id.employee_name", read_only=True)
    operator_name = serializers.CharField(source="operator_id.employee_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.employee_name", read_only=True)
    extra_operator_names = serializers.SerializerMethodField(read_only=True)
    driver_designation = serializers.SerializerMethodField(read_only=True)
    operator_designation = serializers.SerializerMethodField(read_only=True)
    corporation_name = serializers.SerializerMethodField(read_only=True)

    extra_operator_id = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False
    )

    @staticmethod
    def _ref(obj, attr, label_attr="name"):
        value = getattr(obj, attr, None)
        if not value:
            return None
        return {"unique_id": getattr(value, "unique_id", None), label_attr: getattr(value, label_attr, None)}

    def get_state(self, obj):
        return self._ref(obj, "state")

    def get_district(self, obj):
        return self._ref(obj, "district")

    def get_area_type(self, obj):
        return self._ref(obj, "area_type")

    def get_corporation(self, obj):
        return self._ref(obj, "corporation", "corporation_name")

    def get_municipality(self, obj):
        return self._ref(obj, "municipality", "municipality_name")

    def get_town_panchayat(self, obj):
        return self._ref(obj, "town_panchayat", "town_panchayat_name")

    def get_panchayat_union(self, obj):
        return self._ref(obj, "panchayat_union", "union_name")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat", "panchayat_name")

    @staticmethod
    def _staff_designation(staff):
        if not staff:
            return None
        designation = getattr(staff, "designation_id", None)
        if designation and getattr(designation, "designation_name", None):
            return designation.designation_name
        return getattr(staff, "designation", None)

    @staticmethod
    def _staff_corporation(staff):
        if not staff:
            return None
        corporation = getattr(staff, "corporation", None)
        if corporation and getattr(corporation, "corporation_name", None):
            return corporation.corporation_name
        return None

    def get_driver_designation(self, obj):
        return self._staff_designation(getattr(obj, "driver_id", None))

    def get_operator_designation(self, obj):
        return self._staff_designation(getattr(obj, "operator_id", None))

    def get_corporation_name(self, obj):
        # Prefer the template's own corporation; fall back to the driver's,
        # then the operator's (for older templates without geo assigned).
        template_corp = getattr(obj, "corporation", None)
        if template_corp and getattr(template_corp, "corporation_name", None):
            return template_corp.corporation_name
        return (
            self._staff_corporation(getattr(obj, "driver_id", None))
            or self._staff_corporation(getattr(obj, "operator_id", None))
        )

    def get_extra_operator_names(self, obj):
        extra_ids = getattr(obj, "extra_operator_id", None) or []
        if not isinstance(extra_ids, list):
            return []

        normalized_ids = [str(item) for item in extra_ids if item not in ("", None)]
        if not normalized_ids:
            return []

        staff_by_id = {
            staff.staff_unique_id: staff
            for staff in Staffcreation.objects.filter(
                staff_unique_id__in=normalized_ids,
                is_deleted=False,
            )
        }

        names = []
        for staff_id in normalized_ids:
            staff = staff_by_id.get(staff_id)
            if staff and getattr(staff, "employee_name", None):
                names.append(staff.employee_name)
            else:
                names.append(staff_id)
        return names

    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffTemplate
        fields = [
            "unique_id",

            "display_code",

            "driver_id",
            "driver_name",
            "driver_designation",
            # "driver_role",

            "operator_id",
            "operator_name",
            "operator_designation",
            # "operator_role",

            "extra_operator_id",
            "extra_operator_names",

            # Geo hierarchy — write via *_id, read via nested objects
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",

            "corporation_name",

            "staffusertype_name",

            "created_by",
            

            "updated_by",
        

            "approved_by",
            "approved_by_name",

            "status",
            "approval_status",

            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
            "driver_name",
            "operator_name",
            "extra_operator_names",
            "driver_designation",
            "operator_designation",
            "corporation_name",
            "driver_role",
            "operator_role",
            "created_by_name",
            "updated_by_name",
            "approved_by_name",
        ]

    def validate_approved_by(self, value):
        if self.instance and self.instance.approved_by and self.instance.approved_by != value:
            raise serializers.ValidationError("Approved by cannot be modified")
        return value

    def validate(self, attrs):
        errors = normalize_flat_geo_attrs(
            attrs,
            instance=getattr(self, "instance", None),
            require_geo=True,
        )
        if errors:
            raise serializers.ValidationError(errors)

        driver = attrs.get("driver_id", getattr(self.instance, "driver_id", None) if self.instance else None)
        operator = attrs.get("operator_id", getattr(self.instance, "operator_id", None) if self.instance else None)
        if driver and operator and driver == operator:
            raise serializers.ValidationError("Driver and Operator cannot be the same user.")

        extra_operator = attrs.get("extra_operator_id")
        if extra_operator is None and self.instance:
            extra_operator = self.instance.extra_operator_id

        if extra_operator is not None:
            if not isinstance(extra_operator, list):
                raise serializers.ValidationError({"extra_operator_id": "Expected a list of user IDs."})

            extra_ids = [str(item) for item in extra_operator if item not in ("", None)]
            if len(extra_ids) != len(set(extra_ids)):
                raise serializers.ValidationError({"extra_operator_id": "Duplicate users are not allowed."})

            driver_id = getattr(driver, "staff_unique_id", None) if driver else None
            operator_id = getattr(operator, "staff_unique_id", None) if operator else None
            if driver_id and driver_id in extra_ids:
                raise serializers.ValidationError({"extra_operator_id": "Extra staff cannot include the primary driver."})
            if operator_id and operator_id in extra_ids:
                raise serializers.ValidationError({"extra_operator_id": "Extra staff cannot include the primary operator."})

            if extra_ids:
                found_ids = set(
                    Staffcreation.objects.filter(
                        staff_unique_id__in=extra_ids,
                        is_deleted=False,
                    ).values_list("staff_unique_id", flat=True)
                )
                missing_ids = sorted(set(extra_ids) - found_ids)
                if missing_ids:
                    raise serializers.ValidationError({
                        "extra_operator_id": f"Unknown user IDs: {', '.join(missing_ids)}."
                    })

            attrs["extra_operator_id"] = extra_ids

        return attrs
