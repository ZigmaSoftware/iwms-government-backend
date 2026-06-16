from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class TripPlanStopInputSerializer(serializers.Serializer):
    collection_point_id = serializers.CharField()
    bin_id = serializers.CharField()
    sequence = serializers.IntegerField(min_value=1)
    is_active = serializers.BooleanField(default=True)


class TripPlanSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    company_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    project_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    district_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=District.objects.filter(is_deleted=False),
        write_only=True,
    )
    city_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=City.objects.filter(is_deleted=False),
        write_only=True,
    )
    zone_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Zone.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    panchayat_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    ward_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.filter(is_deleted=False),
        write_only=True,
    )
    vehicle_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        write_only=True,
    )
    supervisor_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        write_only=True,
    )
    property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Property.objects.filter(is_deleted=False),
        write_only=True,
    )
    sub_property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=SubProperty.objects.filter(is_deleted=False),
        write_only=True,
    )
    waste_type_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        write_only=True,
    )

    collection_points = TripPlanStopInputSerializer(
        many=True,
        write_only=True,
        required=False,
    )

    is_auto_assign = serializers.BooleanField(required=False)
    repeat_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_null=True,
    )

    district = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    zone = serializers.SerializerMethodField()
    panchayat = serializers.SerializerMethodField()
    ward = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    sub_property = serializers.SerializerMethodField()
    waste_type = serializers.SerializerMethodField()
    plan_collection_points = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "unique_id",
            "display_code",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "company_id_input",
            "project_id_input",
            "district_id",
            "city_id",
            "zone_id",
            "panchayat_id",
            "ward_id",
            "staff_template_id",
            "vehicle_id",
            "supervisor_id",
            "property_id",
            "sub_property_id",
            "waste_type_id",
            "district",
            "city",
            "zone",
            "panchayat",
            "ward",
            "staff_template",
            "vehicle",
            "supervisor",
            "property",
            "sub_property",
            "waste_type",
            "trip_trigger_weight_kg",
            "max_vehicle_capacity_kg",
            "scheduled_time",
                "is_auto_assign",
                "repeat_days",
            "approval_status",
            "status",
            "collection_points",
            "plan_collection_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
        ]

    def _ref(self, obj, attr, label_attr="name"):
        value = getattr(obj, attr, None)
        if not value:
            return None
        return {
            "unique_id": getattr(value, "unique_id", None),
            label_attr: getattr(value, label_attr, None),
        }

    def get_district(self, obj):
        return self._ref(obj, "district_id")

    def get_city(self, obj):
        return self._ref(obj, "city_id")

    def get_zone(self, obj):
        return self._ref(obj, "zone_id")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat_id", "panchayat_name")

    def get_ward(self, obj):
        return self._ref(obj, "ward_id", "ward_name")

    def get_staff_template(self, obj):
        st = obj.staff_template_id
        if not st:
            return None
        return {
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(getattr(st, "driver_id", None), "employee_name", None),
            "operator": getattr(getattr(st, "operator_id", None), "employee_name", None),
        }

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": vehicle.capacity,
        }

    def get_supervisor(self, obj):
        supervisor = obj.supervisor_id
        if not supervisor:
            return None
        return {
            "unique_id": supervisor.staff_unique_id,
            "employee_name": supervisor.employee_name,
        }

    def get_property(self, obj):
        return self._ref(obj, "property_id", "property_name")

    def get_sub_property(self, obj):
        return self._ref(obj, "sub_property_id", "sub_property_name")

    def get_waste_type(self, obj):
        return self._ref(obj, "waste_type_id", "waste_type_name")

    def get_plan_collection_points(self, obj):
        stops = obj.plan_collection_points.filter(is_deleted=False).select_related(
            "collection_point_id",
            "bin_id",
            "customer_id",
        )
        result = []
        for stop in stops:
            cp = stop.collection_point_id
            bin_obj = stop.bin_id
            customer = stop.customer_id
            result.append({
                "unique_id": stop.unique_id,
                "collection_type": stop.collection_type,
                "collection_point_id": stop.collection_point_id_id,
                "collection_point": {
                    "unique_id": cp.unique_id,
                    "cp_name": cp.cp_name,
                } if cp else None,
                "bin_id": stop.bin_id_id,
                "bin": {
                    "unique_id": bin_obj.unique_id,
                    "bin_name": bin_obj.bin_name,
                } if bin_obj else None,
                "customer_id": stop.customer_id_id,
                "customer": {
                    "unique_id": customer.unique_id,
                    "customer_name": customer.customer_name,
                } if customer else None,
                "sequence": stop.sequence,
                "is_active": stop.is_active,
            })
        return result

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        instance = getattr(self, "instance", None)
        panchayat = attrs.get("panchayat_id", getattr(instance, "panchayat_id", None))
        ward = attrs.get("ward_id", getattr(instance, "ward_id", None))
        if bool(panchayat) == bool(ward):
            raise serializers.ValidationError(
                "Trip plan must belong to either a ward or a panchayat."
            )

        trigger = attrs.get(
            "trip_trigger_weight_kg",
            getattr(instance, "trip_trigger_weight_kg", None),
        )
        capacity = attrs.get(
            "max_vehicle_capacity_kg",
            getattr(instance, "max_vehicle_capacity_kg", None),
        )
        if trigger is not None and capacity is not None and trigger >= capacity:
            raise serializers.ValidationError(
                "Trigger weight must be less than vehicle capacity."
            )

        property_obj = attrs.get("property_id", getattr(instance, "property_id", None))
        sub_property_obj = attrs.get(
            "sub_property_id",
            getattr(instance, "sub_property_id", None),
        )
        if (
            property_obj
            and sub_property_obj
            and sub_property_obj.property_id != property_obj
        ):
            raise serializers.ValidationError(
                "Sub-property does not belong to the selected property."
            )

        stops = attrs.get("collection_points")
        if stops is not None:
            sequences = [stop["sequence"] for stop in stops]
            if len(sequences) != len(set(sequences)):
                raise serializers.ValidationError(
                    {"collection_points": "Stop sequences must be unique."}
                )
            collection_point_ids = [stop["collection_point_id"] for stop in stops]
            if len(collection_point_ids) != len(set(collection_point_ids)):
                raise serializers.ValidationError(
                    {"collection_points": "Collection points must be unique per trip plan."}
                )
            for stop in stops:
                cp = Collection_point.objects.filter(
                    unique_id=stop["collection_point_id"],
                    is_deleted=False,
                ).first()
                bin_obj = Bins.objects.filter(
                    unique_id=stop["bin_id"],
                    is_deleted=False,
                ).first()
                if not cp:
                    raise serializers.ValidationError(
                        {"collection_points": "Invalid collection point."}
                    )
                if not bin_obj or bin_obj.collection_point_id != cp:
                    raise serializers.ValidationError(
                        {"collection_points": "Selected bin does not belong to the collection point."}
                    )

        return attrs

    def _sync_stops(self, trip_plan, stops):
        if stops is None:
            return

        TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan).update(
            is_deleted=True,
            is_active=False,
        )
        for stop in stops:
            cp = Collection_point.objects.get(unique_id=stop["collection_point_id"])
            bin_obj = Bins.objects.get(unique_id=stop["bin_id"])
            TripPlanCollectionPoint.objects.create(
                trip_plan_id=trip_plan,
                collection_point_id=cp,
                bin_id=bin_obj,
                sequence=stop["sequence"],
                is_active=stop.get("is_active", True),
            )

    def create(self, validated_data):
        stops = validated_data.pop("collection_points", None)
        trip_plan = super().create(validated_data)
        self._sync_stops(trip_plan, stops)
        return trip_plan

    def update(self, instance, validated_data):
        stops = validated_data.pop("collection_points", None)
        trip_plan = super().update(instance, validated_data)
        self._sync_stops(trip_plan, stops)
        return trip_plan
