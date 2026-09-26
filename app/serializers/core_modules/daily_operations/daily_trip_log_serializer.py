from django.utils import timezone
from rest_framework import serializers

from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.plain_ref import ref_value
from app.utils.plain_ref import ref_id
from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.hierarchy import flat_geo_display
from app.utils.waste_images import capture_images_for_customer


class DailyTripLogSerializer(serializers.ModelSerializer):
    # Plain unique_id references (no DB relation); validated below.
    trip_assignment_id = serializers.CharField(write_only=True)
    bin_ids = serializers.SlugRelatedField(
        source="bins",
        slug_field="unique_id",
        queryset=Bins.objects.all(),  # allow historical refs to soft-deleted bins
        many=True,
        required=False,
    )
    extra_operator_ids = serializers.SlugRelatedField(
        source="extra_operators",
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )
    verified_by = serializers.CharField(source="verified_by_id", read_only=True)

    trip_assignment = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    waste_types_detail = serializers.SerializerMethodField(read_only=True)
    waste_type_breakdown = serializers.SerializerMethodField(read_only=True)
    driver = serializers.SerializerMethodField(read_only=True)
    operator = serializers.SerializerMethodField(read_only=True)
    extra_operators = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    bins = serializers.SerializerMethodField(read_only=True)
    verified_by_name = serializers.SerializerMethodField(read_only=True)
    collection_status = serializers.SerializerMethodField(read_only=True)
    household_collections = serializers.SerializerMethodField(read_only=True)
    capture_images = serializers.SerializerMethodField(read_only=True)
    wards_detail = serializers.SerializerMethodField(read_only=True)

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
            "wards_detail",
            "collection_point_id",
            "collection_point",
            "collection_points",
            "waste_types_detail",
            "waste_type_breakdown",
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
        assignment = obj.trip_assignment
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan", None)
        return {
            "unique_id": assignment.unique_id,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "display_code": getattr(trip_plan, "display_code", assignment.unique_id),
        }

    def get_wards_detail(self, obj):
        return [
            {"unique_id": ward.unique_id, "ward_name": ward.ward_name}
            for ward in obj.trip_assignment.wards.all()
        ] if obj.trip_assignment else []

    def get_staff_template(self, obj):
        # Fall back to trip assignment's templates for records created before the migration
        assignment = obj.trip_assignment
        template = obj.staff_template or getattr(assignment, "staff_template", None)
        alt = obj.alt_staff_template or getattr(assignment, "alt_staff_template", None)
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
                "driver": self._staff_dict(getattr(template, "driver", None)),
                "operator": self._staff_dict(getattr(template, "operator", None)),
            }
        if alt:
            result["alt"] = {
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": self._staff_dict(getattr(alt, "driver", None)),
                "operator": self._staff_dict(getattr(alt, "operator", None)),
            }
        return result

    def _retrip_remarks_by_new_assignment(self, assignment):
        """new_assignment_id -> why the stops that carried over there did so.

        Remarks are mandatory when a trip proceeds to a next trip (see
        DailyTripAssignmentViewSet.proceed_next_trip / retrip_service), but
        `carried_to_assignment` alone is just an id — this is what lets the
        Trip Log report/verify screens show the actual reason next to it.
        Prefers the supervisor's review remarks (what closed the trip) over
        the original driver-raised reason, falling back to it when blank —
        in the one-step web flow the two are identical anyway.
        """
        from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest

        # new_assignment_id holds the continuation's unique_id, the same
        # value every carried stop's `carried_to_assignment_id` holds.
        rows = TripRetripRequest.objects.filter(
            assignment_id=ref_id(assignment),
            status=TripRetripRequest.STATUS_APPROVED,
            new_assignment_id__isnull=False,
        ).values("new_assignment_id", "review_remarks", "reason")
        return {
            row["new_assignment_id"]: (row["review_remarks"] or row["reason"] or "")
            for row in rows
        }

    def get_collection_points(self, obj):
        from django.db.models import Sum
        from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent

        assignment = obj.trip_assignment
        if not assignment:
            return []
        retrip_remarks = self._retrip_remarks_by_new_assignment(assignment)
        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .order_by("sequence")
        )
        cp_ids = [tcp.unique_id for tcp in cps]
        breakdown_by_cp = {}
        if cp_ids:
            event_rows = (
                BinCollectionEvent.objects.filter(
                    trip_collection_point_id__in=cp_ids, is_deleted=False
                )
                .annotate(waste_type_name=ref_value("waste_type_id", WasteType, "waste_type_name"))
                .values("trip_collection_point_id", "waste_type_id", "waste_type_name")
                .annotate(total_weight=Sum("collected_weight_kg"))
            )
            for row in event_rows:
                if not row["total_weight"]:
                    continue
                breakdown_by_cp.setdefault(row["trip_collection_point_id"], []).append(
                    {
                        "waste_type_id": row["waste_type_id"],
                        "waste_type_name": row["waste_type_name"],
                        "collected_weight_kg": str(row["total_weight"]),
                    }
                )
        return [
            {
                "unique_id": tcp.collection_point.unique_id,
                # The DailyTripCollectionPoint (stop) id — distinct from
                # "unique_id" above, which is the Collection_point MASTER's
                # id. `proceed-next-trip`'s `collection_point_ids` expects
                # this one (it matches against DailyTripCollectionPoint rows,
                # see retrip_service.approve_retrip), so the web UI's carry-
                # over checkbox must key off this field, not "unique_id".
                "trip_collection_point_id": tcp.unique_id,
                "cp_name": tcp.collection_point.cp_name,
                "sequence": tcp.sequence,
                "is_collected": tcp.is_collected,
                "status": tcp.status,
                "collected_at": tcp.collected_at.isoformat() if tcp.collected_at else None,
                "collected_weight_kg": (
                    str(tcp.collected_weight_kg)
                    if tcp.collected_weight_kg is not None
                    else None
                ),
                "waste_type_name": getattr(getattr(tcp.bin_id, "wastetype", None), "waste_type_name", None),
                "waste_type_breakdown": breakdown_by_cp.get(tcp.unique_id, []),
                "carried_to_assignment": tcp.carried_to_assignment_id,
                "carried_to_assignment_remarks": retrip_remarks.get(tcp.carried_to_assignment_id),
            }
            for tcp in cps
            if tcp.collection_point_id
        ]

    def get_collection_status(self, obj):
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        assignment = obj.trip_assignment
        if not assignment:
            return "Not Started"

        # The assignment's own status is authoritative once the trip has
        # actually ended — including via a Re-Trip (`mark_ended()` on the
        # source trip when its leftover stops are carried to a continuation).
        # Falling back to a stop-count tally in that case would show "In
        # Progress" forever, since carried-over stops are deliberately left
        # Pending rather than force-resolved (see retrip_service.approve_retrip).
        if assignment.status == DailyTripAssignment.STATUS_COMPLETED:
            return "Completed"

        bin_stops = [cp for cp in assignment.trip_collection_points.all() if not cp.is_deleted]
        hh_stops = list(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment.unique_id, is_deleted=False
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
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.utils.waste_type_breakdown import HOUSEHOLD_WASTE_TYPE_NAMES

        assignment = obj.trip_assignment
        if not assignment:
            return []
        retrip_remarks = self._retrip_remarks_by_new_assignment(assignment)
        hh_list = (
            DailyTripHouseholdCollection.objects
            .filter(trip_assignment_id=assignment.unique_id, is_deleted=False)
            .order_by("sequence")
        )
        result = []
        for hh in hh_list:
            customer = hh.customer
            wc = hh.waste_collection
            waste_type_breakdown = []
            for column, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
                value = getattr(wc, column, None) if wc else None
                if not value:
                    continue
                waste_type_breakdown.append(
                    {
                        "waste_type_id": None,
                        "waste_type_name": label,
                        "collected_weight_kg": str(value),
                    }
                )
            result.append({
                "unique_id": hh.unique_id,
                "sequence": hh.sequence,
                "customer_name": getattr(customer, "customer_name", None) if customer else None,
                "customer_unique_id": getattr(customer, "unique_id", None) if customer else None,
                "is_collected": hh.is_collected,
                "collected_weight_kg": (
                    str(hh.collected_weight_kg) if hh.collected_weight_kg is not None else None
                ),
                "wet_waste": getattr(wc, "wet_waste", None),
                "dry_waste": getattr(wc, "dry_waste", None),
                "mixed_waste": getattr(wc, "mixed_waste", None),
                "sanitary_waste": getattr(wc, "sanitary_waste", None),
                "waste_type_breakdown": waste_type_breakdown,
                "collected_at": hh.collected_at.isoformat() if hh.collected_at else None,
                "status": hh.status,
                "carried_to_assignment": hh.carried_to_assignment_id,
                "carried_to_assignment_remarks": retrip_remarks.get(hh.carried_to_assignment_id),
            })
        return result

    def get_capture_images(self, obj):
        """Capture photos taken during this trip — aggregated from every
        WasteCollection recorded against the trip assignment (each links to its
        household's WasteCollectionSub photos)."""
        from app.models.core_modules.daily_operations.waste_collection import WasteCollection

        assignment_id = obj.trip_assignment
        if not assignment_id:
            return []
        request = self.context.get("request")
        images = []
        seen = set()
        collections = WasteCollection.objects.filter(
            trip_assignment_id=ref_id(assignment_id), is_deleted=False
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
        # Full location detail straight from the geo master columns on the log
        # (falling back to its assignment) — these are now plain unique_id
        # strings (no DB relation), so resolve display names with a lookup
        # instead of attribute-chaining a live FK.
        source = obj if obj.district_id or obj.panchayat_id or obj.corporation_id else obj.trip_assignment
        if not source:
            source = obj
        name, level = flat_geo_display(source)
        area_type_name = AreaType.objects.filter(
            unique_id=getattr(source, "area_type_id", None)
        ).values_list("name", flat=True).first()
        district_name = District.objects.filter(
            unique_id=getattr(source, "district_id", None)
        ).values_list("name", flat=True).first()
        state_name = State.objects.filter(
            unique_id=getattr(source, "state_id", None)
        ).values_list("name", flat=True).first()
        return {
            "state": state_name,
            "district": district_name,
            # "Urban Local Body" / "Rural Local Body" from the AreaType master
            "classification": area_type_name,
            "local_body_name": name,
            "local_body_level": level,
        }

    def get_collection_point(self, obj):
        cp = obj.collection_point
        return None if not cp else {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_types_detail(self, obj):
        return [{"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name} for wt in obj.waste_types.all()]

    def get_waste_type_breakdown(self, obj):
        from app.utils.waste_type_breakdown import waste_type_breakdown_for_assignment
        assignment = obj.trip_assignment
        if not assignment:
            return []
        return waste_type_breakdown_for_assignment(assignment)

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "staff_unique_id": staff.staff_unique_id,
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def get_driver(self, obj):
        return self._staff_dict(obj.driver)

    def get_operator(self, obj):
        return self._staff_dict(obj.operator)

    def get_extra_operators(self, obj):
        return [self._staff_dict(staff) for staff in obj.extra_operators]

    def get_vehicle(self, obj):
        vehicle = obj.vehicle
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
            for bin_obj in obj.bins
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

        assignment_uid = attrs.get(
            "trip_assignment_id",
            getattr(instance, "trip_assignment_id", None),
        )
        assignment = (
            DailyTripAssignment.objects.filter(unique_id=assignment_uid, is_deleted=False).first()
            if assignment_uid
            else None
        )
        if assignment_uid and assignment is None:
            raise serializers.ValidationError(
                {"trip_assignment_id": f"Object with unique_id={assignment_uid} does not exist."}
            )
        if assignment and assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError("Cannot create a log for a cancelled trip.")

        if assignment and not instance:
            if DailyTripLog.objects.filter(trip_assignment_id=ref_id(assignment), is_deleted=False).exists():
                raise serializers.ValidationError("A log already exists for this trip assignment.")

        start_time = attrs.get("actual_start_time", getattr(instance, "actual_start_time", None))
        end_time = attrs.get("actual_end_time", getattr(instance, "actual_end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("actual_end_time must be after actual_start_time.")

        # Bins / extra operators are stored as plain unique_id lists.
        if "bins" in attrs:
            attrs["bin_ids"] = [b.unique_id for b in attrs.pop("bins")]
        if "extra_operators" in attrs:
            attrs["extra_operator_ids"] = [st.staff_unique_id for st in attrs.pop("extra_operators")]
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
