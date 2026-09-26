from rest_framework import serializers

from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.hierarchy import BARE_TO_ID_GEO_FIELDS, FLAT_GEO_FIELDS, normalize_flat_geo_attrs
from app.utils import ref_cache





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


    # Plain unique_id references (no DB relation); checked in validate_*.
    staff_template = serializers.CharField(source="staff_template_id")
    driver = serializers.CharField(source="driver_id")
    operator = serializers.CharField(source="operator_id")
    # requested_by = UniqueIdOrPkField(
    #     slug_field="staff_unique_id",
    #     queryset=Staffcreation.objects.filter(is_deleted=False),
    #     required=False,
    # )
    approved_by = serializers.CharField(
        source="approved_by_id", required=False, allow_null=True
    )

    @staticmethod
    def _active_staff_id(value):
        if not Staffcreation.objects.filter(staff_unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with staff_unique_id={value} does not exist.")
        return value

    def validate_staff_template(self, value):
        if not StaffTemplate.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_driver(self, value):
        return self._active_staff_id(value)

    def validate_operator(self, value):
        return self._active_staff_id(value)

    def validate_approved_by(self, value):
        return self._active_staff_id(value) if value else None
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

    # ---- Geo hierarchy: plain unique_id strings in, display refs out ----
    # AlternativeStaffTemplate's own columns are literally named "<field>_id"
    # (CharField, no DB relation) — same convention as Ward/Corporation/etc —
    # so these input fields need no `source=` override.
    state_id = serializers.CharField(required=False, allow_null=True)
    district_id = serializers.CharField(required=False, allow_null=True)
    area_type_id = serializers.CharField(required=False, allow_null=True)
    corporation_id = serializers.CharField(required=False, allow_null=True)
    municipality_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_id = serializers.CharField(required=False, allow_null=True)

    state = serializers.SerializerMethodField(read_only=True)
    district = serializers.SerializerMethodField(read_only=True)
    area_type = serializers.SerializerMethodField(read_only=True)
    corporation = serializers.SerializerMethodField(read_only=True)
    municipality = serializers.SerializerMethodField(read_only=True)
    town_panchayat = serializers.SerializerMethodField(read_only=True)
    panchayat_union = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)

    _GEO_REF_MODELS = {
        "state": (State, "name"),
        "district": (District, "name"),
        "area_type": (AreaType, "name"),
        "corporation": (Corporation, "corporation_name"),
        "municipality": (Municipality, "municipality_name"),
        "town_panchayat": (TownPanchayat, "town_panchayat_name"),
        "panchayat_union": (PanchayatUnion, "union_name"),
        "panchayat": (Panchayat, "panchayat_name"),
    }

    @classmethod
    def _ref(cls, obj, field, label_attr=None):
        value = getattr(obj, f"{field}_id", None)
        if not value:
            return None
        model, default_label_attr = cls._GEO_REF_MODELS[field]
        label_attr = label_attr or default_label_attr
        instance = ref_cache.get(model, value, "unique_id")
        if not instance:
            return None
        return {"unique_id": instance.unique_id, label_attr: getattr(instance, label_attr, None)}

    def get_state(self, obj):
        return self._ref(obj, "state")

    def get_district(self, obj):
        return self._ref(obj, "district")

    def get_area_type(self, obj):
        return self._ref(obj, "area_type")

    def get_corporation(self, obj):
        return self._ref(obj, "corporation")

    def get_municipality(self, obj):
        return self._ref(obj, "municipality")

    def get_town_panchayat(self, obj):
        return self._ref(obj, "town_panchayat")

    def get_panchayat_union(self, obj):
        return self._ref(obj, "panchayat_union")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat")

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
        if not staff or not getattr(staff, "corporation_id", None):
            return None
        return (
            Corporation.objects.filter(unique_id=staff.corporation_id)
            .values_list("corporation_name", flat=True)
            .first()
        )

    def get_driver_designation(self, obj):
        return self._staff_designation(obj.driver)

    def get_operator_designation(self, obj):
        return self._staff_designation(obj.operator)

    def get_corporation_name(self, obj):
        template_corp_name = None
        if getattr(obj, "corporation_id", None):
            template_corp_name = getattr(ref_cache.get(Corporation, obj.corporation_id, "unique_id"), "corporation_name", None)
        return (
            template_corp_name
            or self._staff_corporation(obj.driver)
            or self._staff_corporation(obj.operator)
        )
    staff_template_display_code = serializers.CharField(
        source="staff_template.display_code",
        read_only=True,
        default=None,
    )
    display_code = serializers.CharField(read_only=True)

    def get_driver_name(self, obj):
        staff = obj.driver
        if staff and getattr(staff, "employee_name", None):
            return staff.employee_name
        return obj.driver_id

    def get_operator_name(self, obj):
        staff = obj.operator
        if staff and getattr(staff, "employee_name", None):
            return staff.employee_name
        return obj.operator_id

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

        staff_template_uid = attrs.get(
            "staff_template_id", getattr(instance, "staff_template_id", None)
        )
        staff_template = (
            StaffTemplate.objects.filter(unique_id=staff_template_uid).first()
            if staff_template_uid
            else None
        )
        # `normalize_flat_geo_attrs` is shared with still-FK-based callers and
        # works in terms of the bare geo-level names ("state", "corporation",
        # ...) both for reading `attrs`/`instance` and for the keys it writes
        # back. AlternativeStaffTemplate's own model fields (and
        # StaffTemplate's, when defaulting from it below) are the
        # "_id"-suffixed plain CharFields, so translate both ways.
        bare_attrs = dict(attrs)
        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if real in bare_attrs:
                bare_attrs[bare] = bare_attrs.pop(real)

        if staff_template:
            has_explicit_geo = any(field in bare_attrs for field in FLAT_GEO_FIELDS)
            has_existing_geo = any(
                getattr(instance, f"{field}_id", None) for field in FLAT_GEO_FIELDS
            ) if instance else False
            if not has_explicit_geo and not has_existing_geo:
                for field in FLAT_GEO_FIELDS:
                    bare_attrs[field] = getattr(staff_template, f"{field}_id", None)

        errors = normalize_flat_geo_attrs(
            bare_attrs,
            instance=instance,
            require_geo=True,
            as_strings=True,
        )
        if errors:
            raise serializers.ValidationError(errors)

        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if bare in bare_attrs:
                attrs[real] = bare_attrs.pop(bare)
        attrs.update(bare_attrs)

        if staff_template and from_date and to_date:
            overlap_qs = AlternativeStaffTemplate.objects.filter(
                staff_template_id=staff_template.unique_id,
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

            driver_id = driver or None
            operator_id = operator or None

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
