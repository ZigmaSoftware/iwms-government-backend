from rest_framework import serializers

from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
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
from app.utils.hierarchy import FLAT_GEO_FIELDS, normalize_flat_geo_attrs





class CommaSeparatedListField(serializers.ListField):
    """
    Accepts comma-separated strings or repeated form-data keys and
    normalises them into a clean list.
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [item.strip() for item in data.split(",") if item.strip()]
        elif isinstance(data, (list, tuple)):
            normalized = []
            for item in data:
                if item in ("", None):
                    continue
                if isinstance(item, str):
                    normalized.extend([part.strip() for part in item.split(",") if part.strip()])
                else:
                    normalized.append(item)
            data = normalized
        return super().to_internal_value(data)

    def to_representation(self, value):
        if value is None:
            return []
        return super().to_representation(value)


class AlternativeStaffTemplateSerializer(serializers.ModelSerializer):


    staff_template = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all(),
    )
    driver = UniqueIdOrPkField(
        source="driver_id",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )
    operator = UniqueIdOrPkField(
        source="operator_id",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )
    # requested_by = UniqueIdOrPkField(
    #     slug_field="staff_unique_id",
    #     queryset=Staffcreation.objects.filter(is_deleted=False),
    #     required=False,
    # )
    approved_by = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    extra_operator = CommaSeparatedListField(
        source="extra_operator_id",
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
    driver_name = serializers.SerializerMethodField(read_only=True)
    operator_name = serializers.SerializerMethodField(read_only=True)
    extra_operator_names = serializers.SerializerMethodField(read_only=True)
    driver_designation = serializers.SerializerMethodField(read_only=True)
    operator_designation = serializers.SerializerMethodField(read_only=True)
    corporation_name = serializers.SerializerMethodField(read_only=True)

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
        template_corp = getattr(obj, "corporation", None)
        if template_corp and getattr(template_corp, "corporation_name", None):
            return template_corp.corporation_name
        return (
            self._staff_corporation(getattr(obj, "driver_id", None))
            or self._staff_corporation(getattr(obj, "operator_id", None))
        )
    staff_template_display_code = serializers.CharField(
        source="staff_template.display_code",
        read_only=True,
    )
    display_code = serializers.CharField(read_only=True)

    def get_driver_name(self, obj):
        staff = getattr(obj, "driver_id", None)
        if staff and hasattr(staff, 'employee_name') and staff.employee_name:
            return staff.employee_name
        return getattr(staff, "staff_unique_id", None)

    def get_operator_name(self, obj):
        staff = getattr(obj, "operator_id", None)
        if staff and hasattr(staff, 'employee_name') and staff.employee_name:
            return staff.employee_name
        return getattr(staff, "staff_unique_id", None)

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
    
    class Meta:
        model = AlternativeStaffTemplate
        fields = [
            'unique_id',
            'display_code',
            'staff_template',
            'staff_template_display_code',
            'from_date',
            'to_date',
            # 'effective_date',
            'driver',
            'driver_name',
            'driver_designation',
            'operator',
            'operator_name',
            'operator_designation',
            'extra_operator',
            'extra_operator_names',
            # Geo hierarchy — write via *_id, read via nested objects
            'state_id',
            'district_id',
            'area_type_id',
            'corporation_id',
            'municipality_id',
            'town_panchayat_id',
            'panchayat_union_id',
            'panchayat_id',
            'state',
            'district',
            'area_type',
            'corporation',
            'municipality',
            'town_panchayat',
            'panchayat_union',
            'panchayat',
            'corporation_name',
            'change_reason',
            'change_remarks',
            # 'requested_by',
            'approved_by',
            'approval_status',
            'created_at',
        ]
        read_only_fields = [
            'unique_id',
            'display_code',
            'staff_template_display_code',
            'created_at',
        ]

    def validate(self, attrs):
        """
        Hard validation layer.
        Prevents obvious data-quality issues before hitting DB.
        """
        instance = getattr(self, "instance", None)

        # ------------------------------------------------------------------
        # DATE RANGE VALIDATION
        # ------------------------------------------------------------------
        from_date = attrs.get("from_date", getattr(instance, "from_date", None))
        to_date = attrs.get("to_date", getattr(instance, "to_date", None))

        if from_date and to_date and to_date < from_date:
            raise serializers.ValidationError(
                {"to_date": "to_date must be on or after from_date."}
            )

        staff_template = attrs.get(
            "staff_template", getattr(instance, "staff_template", None)
        )
        if staff_template:
            has_explicit_geo = any(field in attrs for field in FLAT_GEO_FIELDS)
            has_existing_geo = any(
                getattr(instance, field, None) for field in FLAT_GEO_FIELDS
            ) if instance else False
            if not has_explicit_geo and not has_existing_geo:
                for field in FLAT_GEO_FIELDS:
                    attrs[field] = getattr(staff_template, field, None)

        errors = normalize_flat_geo_attrs(
            attrs,
            instance=instance,
            require_geo=True,
        )
        if errors:
            raise serializers.ValidationError(errors)

        if staff_template and from_date and to_date:
            overlap_qs = AlternativeStaffTemplate.objects.filter(
                staff_template=staff_template,
                from_date__lte=to_date,
                to_date__gte=from_date,
            )
            if instance:
                overlap_qs = overlap_qs.exclude(unique_id=instance.unique_id)
            if overlap_qs.exists():
                raise serializers.ValidationError(
                    "A substitution already exists for this staff template that "
                    "overlaps the given date range."
                )

        def resolve(source_name):
            if source_name in attrs:
                return attrs.get(source_name)
            return getattr(instance, source_name) if instance else None

        driver = resolve("driver_id")
        operator = resolve("operator_id")

        if driver and operator and driver == operator:
            raise serializers.ValidationError(
                "Driver and Operator cannot be the same user."
            )

        extra_operator = attrs.get("extra_operator_id")
        if extra_operator is None and instance:
            extra_operator = instance.extra_operator_id

        if extra_operator is not None:
            if not isinstance(extra_operator, list):
                raise serializers.ValidationError(
                    {"extra_operator": "Expected a list of user IDs."}
                )

            extra_ids = [str(item) for item in extra_operator if item not in ("", None)]
            if len(extra_ids) != len(set(extra_ids)):
                raise serializers.ValidationError(
                    {"extra_operator": "Duplicate users are not allowed."}
                )

            driver_id = getattr(driver, "staff_unique_id", None) if driver else None
            operator_id = getattr(operator, "staff_unique_id", None) if operator else None

            if driver_id and driver_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra staff cannot include the primary driver."}
                )

            if operator_id and operator_id in extra_ids:
                raise serializers.ValidationError(
                    {"extra_operator": "Extra staff cannot include the primary operator."}
                )

            if extra_ids:
                operators = Staffcreation.objects.filter(
                    staff_unique_id__in=extra_ids,
                    is_deleted=False,
                )
                found_ids = {staff.staff_unique_id for staff in operators}
                missing_ids = sorted(set(extra_ids) - found_ids)
                if missing_ids:
                    raise serializers.ValidationError({
                        "extra_operator": (
                            f"Unknown user IDs: {', '.join(missing_ids)}."
                        )
                    })

            attrs["extra_operator_id"] = extra_ids

        return attrs
