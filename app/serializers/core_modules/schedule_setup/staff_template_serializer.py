from rest_framework import serializers
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
from app.utils.hierarchy import BARE_TO_ID_GEO_FIELDS, normalize_flat_geo_attrs
from app.utils import ref_cache


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(serializers.ModelSerializer):

    # Plain staff_unique_ids (no DB relation); checked in validate_*.
    driver_id = serializers.CharField()
    operator_id = serializers.CharField()
    approved_by = serializers.CharField(
        source="approved_by_id", required=False, allow_null=True
    )

    @staticmethod
    def _active_staff_id(value):
        if not Staffcreation.objects.filter(staff_unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with staff_unique_id={value} does not exist.")
        return value

    def validate_driver_id(self, value):
        return self._active_staff_id(value)

    def validate_operator_id(self, value):
        return self._active_staff_id(value)

    # ---- Geo hierarchy: plain unique_id strings in, display refs out ----
    # StaffTemplate's own columns are literally named "<field>_id" (CharField,
    # no DB relation) — same convention as Ward/Corporation/District/etc —
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

    driver_name = serializers.CharField(source="driver.employee_name", read_only=True, default=None)
    operator_name = serializers.CharField(source="operator.employee_name", read_only=True, default=None)
    approved_by_name = serializers.CharField(source="approved_by.employee_name", read_only=True, default=None)
    extra_operator_names = serializers.SerializerMethodField(read_only=True)
    driver_designation = serializers.SerializerMethodField(read_only=True)
    operator_designation = serializers.SerializerMethodField(read_only=True)
    corporation_name = serializers.SerializerMethodField(read_only=True)

    extra_operator_id = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False
    )

    # (bare geo-level name, model, name attribute) — StaffTemplate's own
    # columns are literally "<field>_id" plain CharFields (unique_id
    # strings, no DB relation), so the reference is resolved by lookup.
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
        # Prefer the template's own corporation; fall back to the driver's,
        # then the operator's (for older templates without geo assigned).
        template_corp_name = None
        if getattr(obj, "corporation_id", None):
            template_corp_name = getattr(ref_cache.get(Corporation, obj.corporation_id, "unique_id"), "corporation_name", None)
        return (
            template_corp_name
            or self._staff_corporation(obj.driver)
            or self._staff_corporation(obj.operator)
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
        if value:
            self._active_staff_id(value)
        if self.instance and self.instance.approved_by_id and self.instance.approved_by_id != value:
            raise serializers.ValidationError("Approved by cannot be modified")
        return value

    def validate(self, attrs):
        # `normalize_flat_geo_attrs` is shared with still-FK-based callers and
        # works in terms of the bare geo-level names ("state", "corporation",
        # ...) both for reading `attrs`/`instance` and for the keys it writes
        # back. StaffTemplate's own model fields are the "_id"-suffixed plain
        # CharFields, so translate both ways around the call.
        bare_attrs = dict(attrs)
        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if real in bare_attrs:
                bare_attrs[bare] = bare_attrs.pop(real)

        errors = normalize_flat_geo_attrs(
            bare_attrs,
            instance=getattr(self, "instance", None),
            require_geo=True,
            as_strings=True,
        )
        if errors:
            raise serializers.ValidationError(errors)

        for bare, real in BARE_TO_ID_GEO_FIELDS.items():
            if bare in bare_attrs:
                attrs[real] = bare_attrs.pop(bare)
        attrs.update(bare_attrs)

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

            driver_id = driver or None
            operator_id = operator or None
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
