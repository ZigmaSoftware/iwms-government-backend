from rest_framework import serializers

from app.utils.plain_ref import ref_id
from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.hierarchy import flat_geo_display, hierarchy_payload


class DailyTripCollectionPointSerializer(
    
    serializers.ModelSerializer,
):
    # Plain unique_id references (no DB relation); checked in validate_*.
    trip_assignment_id = serializers.CharField()
    collection_point_id = serializers.CharField()
    bin_id = serializers.CharField()
    collected_by = serializers.CharField(source="collected_by_id", required=False, allow_null=True)
    carried_to_assignment = serializers.CharField(source="carried_to_assignment_id", read_only=True)

    def validate_trip_assignment_id(self, value):
        if not DailyTripAssignment.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_collection_point_id(self, value):
        if not Collection_point.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_bin_id(self, value):
        if not Bins.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with unique_id={value} does not exist.")
        return value

    def validate_collected_by(self, value):
        if value and not Staffcreation.objects.filter(staff_unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f"Object with staff_unique_id={value} does not exist.")
        return value or None

    trip_assignment = serializers.SerializerMethodField()
    collection_point = serializers.SerializerMethodField()
    bin = serializers.SerializerMethodField()
    collected_by_staff = serializers.SerializerMethodField()
    hierarchy = serializers.SerializerMethodField()

    class Meta:
        model = DailyTripCollectionPoint
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment",
            "collection_point_id",
            "collection_point",
            "hierarchy",
            "bin_id",
            "bin",
            "sequence",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "collected_by",
            "collected_by_staff",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "carried_to_assignment",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "carried_to_assignment",
            "created_at",
            "updated_at",
        ]
        validators = []

    def get_trip_assignment(self, obj):
        assignment = obj.trip_assignment
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan", None)
        return {
            "unique_id": assignment.unique_id,
            "trip_date": assignment.trip_date,
            "scheduled_time": assignment.scheduled_time,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_plan_id": getattr(trip_plan, "unique_id", None),
            "trip_plan_display_code": getattr(trip_plan, "display_code", None),
        }

    def get_collection_point(self, obj):
        cp = obj.collection_point
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            **hierarchy_payload(cp),
            "wards": [{"unique_id": ward.unique_id, "ward_name": ward.ward_name} for ward in cp.wards.all()],
        }

    def get_hierarchy(self, obj):
        name, level = flat_geo_display(obj)
        return {"location_name": name, "location_level": level}

    def get_bin(self, obj):
        bin_obj = obj.bin
        if not bin_obj:
            return None
        waste_type = getattr(bin_obj, "wastetype", None)
        return {
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
            "bin_qr": bin_obj.bin_qr.url if bin_obj.bin_qr else None,
            "waste_type": None if not waste_type else {
                "unique_id": waste_type.unique_id,
                "waste_type_name": waste_type.waste_type_name,
            },
        }

    def get_collected_by_staff(self, obj):
        staff = obj.collected_by
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        assignment = DailyTripAssignment.objects.filter(
            unique_id=attrs.get("trip_assignment_id", getattr(instance, "trip_assignment_id", None))
        ).first()
        collection_point = attrs.get(
            "collection_point_id",
            getattr(instance, "collection_point_id", None),
        )
        bin_obj = Bins.objects.filter(
            unique_id=attrs.get("bin_id", getattr(instance, "bin_id", None))
        ).first()

        if assignment and assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError(
                "Cannot add collection points to a cancelled trip assignment."
            )

        if bin_obj and collection_point and bin_obj.collection_point_id != getattr(
            collection_point, "unique_id", collection_point
        ):
            raise serializers.ValidationError(
                {"bin_id": "Selected bin does not belong to the collection point."}
            )

        if assignment and collection_point:
            conflict = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=ref_id(assignment),
                collection_point_id=ref_id(collection_point),
                bin_id=ref_id(bin_obj),
                is_deleted=False,
            )
            if instance:
                conflict = conflict.exclude(pk=instance.pk)
            if conflict.exists():
                raise serializers.ValidationError(
                    "This bin is already added at this collection point for the trip assignment."
                )

        is_collected = attrs.get(
            "is_collected",
            getattr(instance, "is_collected", False),
        )
        collected_at = attrs.get(
            "collected_at",
            getattr(instance, "collected_at", None),
        )

        if is_collected or collected_at is not None:
            attrs["is_collected"] = True
            attrs["status"] = DailyTripCollectionPoint.STATUS_COLLECTED

        return attrs
