from django.utils import timezone
from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import flat_geo_display
from app.utils.waste_images import capture_images_for_customer


class DailyTripLogSerializer(serializers.ModelSerializer):
    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.select_related(
            "trip_plan_id",
            "trip_plan_id__vehicle_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
            "alt_staff_template_id",
            "alt_staff_template_id__driver_id",
            "alt_staff_template_id__operator_id",
            "district",
            "waste_type_id",
        ).filter(is_deleted=False),
        write_only=True,
    )
    bin_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Bins.objects.all(),  # allow historical refs to soft-deleted bins
        many=True,
        required=False,
    )
    extra_operator_ids = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )

    trip_assignment = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    driver = serializers.SerializerMethodField(read_only=True)
    operator = serializers.SerializerMethodField(read_only=True)
    extra_operators = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    bins = serializers.SerializerMethodField(read_only=True)
    verified_by_name = serializers.SerializerMethodField(read_only=True)
    collection_status = serializers.SerializerMethodField(read_only=True)
    household_collections = serializers.SerializerMethodField(read_only=True)
    capture_images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripLog
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment",
            "staff_template_id",
            "staff_template",
            "alt_staff_template_id",
            "location_name",
            "location_level",
            "location",
            "collection_point_id",
            "collection_point",
            "collection_points",
            "waste_type_id",
            "waste_type",
            "trip_date",
            "actual_start_time",
            "actual_end_time",
            "driver_id",
            "driver",
            "operator_id",
            "operator",
            "extra_operator_ids",
            "extra_operators",
            "collected_weight_kg",
            "household_collected_weight_kg",
            "vehicle_id",
            "vehicle",
            "bin_ids",
            "bins",
            "remarks",
            "log_status",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "collection_status",
            "household_collections",
            "capture_images",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "staff_template_id",
            "alt_staff_template_id",
            "collection_point_id",
            "waste_type_id",
            "trip_date",
            "driver_id",
            "operator_id",
            "vehicle_id",
            "collected_weight_kg",
            "verified_by",
            "verified_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_trip_assignment(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan_id", None)
        return {
            "unique_id": assignment.unique_id,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "display_code": getattr(trip_plan, "display_code", assignment.unique_id),
        }

    def get_staff_template(self, obj):
        # Fall back to trip assignment's templates for records created before the migration
        assignment = obj.trip_assignment_id
        template = obj.staff_template_id or getattr(assignment, "staff_template_id", None)
        alt = obj.alt_staff_template_id or getattr(assignment, "alt_staff_template_id", None)
        if not template and not alt:
            return None
        result = {
            "is_alt": alt is not None,
            "effective_display_code": (alt or template).display_code,
        }
        if template:
            result["base"] = {
                "unique_id": template.unique_id,
                "display_code": template.display_code,
                "driver": self._staff_dict(getattr(template, "driver_id", None)),
                "operator": self._staff_dict(getattr(template, "operator_id", None)),
            }
        if alt:
            result["alt"] = {
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": self._staff_dict(getattr(alt, "driver_id", None)),
                "operator": self._staff_dict(getattr(alt, "operator_id", None)),
            }
        return result

    def get_collection_points(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id")
            .order_by("sequence")
        )
        return [
            {
                "unique_id": tcp.collection_point_id.unique_id,
                "cp_name": tcp.collection_point_id.cp_name,
                "sequence": tcp.sequence,
                "is_collected": tcp.is_collected,
                "collected_weight_kg": (
                    str(tcp.collected_weight_kg)
                    if tcp.collected_weight_kg is not None
                    else None
                ),
            }
            for tcp in cps
            if tcp.collection_point_id
        ]

    def get_collection_status(self, obj):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        assignment = obj.trip_assignment_id
        if not assignment:
            return "Not Started"
        bin_stops = [cp for cp in assignment.trip_collection_points.all() if not cp.is_deleted]
        hh_stops = list(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            )
        )
        total = len(bin_stops) + len(hh_stops)
        if total == 0:
            return "Not Started"
        collected = (
            sum(1 for cp in bin_stops if cp.is_collected)
            + sum(1 for hh in hh_stops if hh.is_collected)
        )
        if collected == 0:
            return "Not Started"
        if collected == total:
            return "Completed"
        return "In Progress"

    def get_household_collections(self, obj):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        hh_list = (
            DailyTripHouseholdCollection.objects
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("customer_id")
            .order_by("sequence")
        )
        result = []
        for hh in hh_list:
            customer = hh.customer_id
            result.append({
                "unique_id": hh.unique_id,
                "sequence": hh.sequence,
                "customer_name": getattr(customer, "customer_name", None) if customer else None,
                "customer_unique_id": getattr(customer, "unique_id", None) if customer else None,
                "is_collected": hh.is_collected,
                "collected_weight_kg": (
                    str(hh.collected_weight_kg) if hh.collected_weight_kg is not None else None
                ),
                "collected_at": hh.collected_at.isoformat() if hh.collected_at else None,
                "status": hh.status,
            })
        return result

    def get_capture_images(self, obj):
        """Capture photos taken during this trip — aggregated from every
        WasteCollection recorded against the trip assignment (each links to its
        household's WasteCollectionSub photos)."""
        from app.models.customers.wastecollection import WasteCollection

        assignment_id = obj.trip_assignment_id_id
        if not assignment_id:
            return []
        request = self.context.get("request")
        images = []
        seen = set()
        collections = WasteCollection.objects.filter(
            trip_assignment_id=assignment_id, is_deleted=False
        )
        for collection in collections:
            for img in capture_images_for_customer(
                collection.customer_id, collection.collection_date, request
            ):
                if img["url"] not in seen:
                    seen.add(img["url"])
                    images.append(img)
        return images

    def get_location_name(self, obj):
        name, _ = flat_geo_display(obj)
        return name

    def get_location_level(self, obj):
        _, level = flat_geo_display(obj)
        return level

    def get_location(self, obj):
        # Full location detail straight from the geo master FKs on the log
        # (falling back to its assignment) — no hierarchy tree/assignment lookup.
        source = obj if obj.district_id or obj.panchayat_id or obj.corporation_id else obj.trip_assignment_id
        if not source:
            source = obj
        name, level = flat_geo_display(source)
        area_type = getattr(source, "area_type", None)
        district = getattr(source, "district", None)
        state = getattr(source, "state", None)
        return {
            "state": getattr(state, "name", None),
            "district": getattr(district, "name", None),
            # "Urban Local Body" / "Rural Local Body" from the AreaType master
            "classification": getattr(area_type, "name", None),
            "local_body_name": name,
            "local_body_level": level,
        }

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        return None if not cp else {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_type(self, obj):
        wt = obj.waste_type_id
        return None if not wt else {"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name}

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "staff_unique_id": staff.staff_unique_id,
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def get_driver(self, obj):
        return self._staff_dict(obj.driver_id)

    def get_operator(self, obj):
        return self._staff_dict(obj.operator_id)

    def get_extra_operators(self, obj):
        return [self._staff_dict(staff) for staff in obj.extra_operator_ids.all()]

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity is not None else None,
        }

    def get_bins(self, obj):
        return [
            {
                "unique_id": bin_obj.unique_id,
                "bin_name": bin_obj.bin_name,
                "bin_status": getattr(bin_obj, "bin_status", None),
            }
            for bin_obj in obj.bin_ids.all()
        ]

    def get_verified_by_name(self, obj):
        account = obj.verified_by
        staff = getattr(account, "staff", None)
        user = getattr(account, "user", None)
        return getattr(staff, "employee_name", None) or getattr(user, "username", None)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Verified trip logs are read-only.")

        assignment = attrs.get(
            "trip_assignment_id",
            getattr(instance, "trip_assignment_id", None),
        )
        if assignment and assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError("Cannot create a log for a cancelled trip.")

        if assignment and not instance:
            if DailyTripLog.objects.filter(trip_assignment_id=assignment, is_deleted=False).exists():
                raise serializers.ValidationError("A log already exists for this trip assignment.")

        start_time = attrs.get("actual_start_time", getattr(instance, "actual_start_time", None))
        end_time = attrs.get("actual_end_time", getattr(instance, "actual_end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("actual_end_time must be after actual_start_time.")

        return attrs


class DailyTripLogVerifySerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        instance = self.context.get("instance")
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Trip log is already verified.")
        return attrs

    def save(self, **kwargs):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks")
        now = timezone.now()

        update_fields = {
            "log_status": DailyTripLog.LOG_STATUS_VERIFIED,
            "verified_by_id": account.pk if account else None,
            "verified_at": now,
            "updated_at": now,
        }
        if remarks:
            update_fields["remarks"] = remarks

        DailyTripLog.objects.filter(pk=instance.pk).update(**update_fields)
        instance.refresh_from_db()
        return instance
