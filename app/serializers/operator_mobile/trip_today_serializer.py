import hashlib

from django.core.cache import cache
from rest_framework import serializers

from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.services.openroute_service import route_stops


class _PanchayatBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="panchayat_name")
    # Panchayat has no lat/lng columns (only a `coordinates` polygon); expose
    # nulls so the mobile client's optional fields stay populated safely.
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    def get_latitude(self, obj):
        return None

    def get_longitude(self, obj):
        return None


class _WasteTypeBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="waste_type_name")


class _VehicleBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    vehicle_no = serializers.CharField()
    capacity = serializers.DecimalField(max_digits=10, decimal_places=2)


class _CollectionPointBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="cp_name")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)


class _BinBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    bin_name = serializers.CharField()
    bin_qr = serializers.SerializerMethodField()
    bin_qr_image_url = serializers.SerializerMethodField()
    bin_capacity = serializers.IntegerField()

    def get_bin_qr(self, obj):
        return obj.unique_id

    def get_bin_qr_image_url(self, obj):
        qr = getattr(obj, "bin_qr", None)
        try:
            url = qr.url if qr else None
        except (ValueError, AttributeError):
            url = None
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class TripCollectionPointSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    sequence = serializers.IntegerField()
    is_collected = serializers.BooleanField()
    status = serializers.CharField()
    status_reason = serializers.CharField(allow_null=True, required=False)
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    collection_point = _CollectionPointBriefSerializer(source="collection_point_id")
    bin = _BinBriefSerializer(source="bin_id")


class MyTripTodaySerializer(serializers.Serializer):
    assignment_unique_id = serializers.CharField(source="unique_id")
    trip_date = serializers.DateField()
    status = serializers.CharField()
    # bin_collection / household_collection / bulk_waste_collection — drives the
    # collection-type pill on the mobile trip header.
    collection_type = serializers.SerializerMethodField()
    scheduled_time = serializers.TimeField()
    actual_start_time = serializers.TimeField(allow_null=True)
    actual_end_time = serializers.TimeField(allow_null=True)
    panchayat = _PanchayatBriefSerializer()
    waste_type = _WasteTypeBriefSerializer(source="waste_type_id")
    vehicle = _VehicleBriefSerializer(source="vehicle_id", allow_null=True)
    progress = serializers.SerializerMethodField()
    distance_meters = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    route_geojson = serializers.SerializerMethodField()
    vehicle_start = serializers.SerializerMethodField()
    collection_points = serializers.SerializerMethodField()
    # Household stops (customers) for household/bulk trips — the driver collects
    # each household directly rather than scanning a bin.
    household_collections = serializers.SerializerMethodField()

    _HOUSEHOLD_TYPES = ("household_collection", "bulk_waste_collection")

    def get_collection_type(self, obj):
        plan = getattr(obj, "trip_plan_id", None)
        return getattr(plan, "collection_type", None)

    def _household_rows(self, obj):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        return list(
            DailyTripHouseholdCollection.objects
            .filter(trip_assignment_id=obj, is_deleted=False)
            .select_related("customer_id")
            .order_by("sequence")
        )

    def get_progress(self, obj):
        # Household/bulk trips have no bin CPs — measure progress by households.
        if self.get_collection_type(obj) in self._HOUSEHOLD_TYPES:
            from app.models.schedule_masters.daily_trip_household_collection import (
                DailyTripHouseholdCollection,
            )

            rows = self._household_rows(obj)
            total = len(rows)
            collected = sum(1 for h in rows if h.is_collected)
            resolved = sum(
                1 for h in rows
                if h.is_collected
                or h.status in {
                    DailyTripHouseholdCollection.STATUS_MISSED,
                    DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
                }
            )
            return {
                "collected": collected,
                "total": total,
                "resolved": resolved,
                "completed": total > 0 and resolved == total,
            }

        children = list(
            obj.trip_collection_points.filter(is_deleted=False)
        )
        total = len(children)
        collected = sum(
            1 for c in children
            if c.status == DailyTripCollectionPoint.STATUS_COLLECTED
        )
        resolved = sum(
            1 for c in children
            if c.status in {
                DailyTripCollectionPoint.STATUS_COLLECTED,
                DailyTripCollectionPoint.STATUS_MISSED,
            }
        )
        return {
            "collected": collected,
            "total": total,
            "resolved": resolved,
            "completed": total > 0 and resolved == total,
        }

    def get_household_collections(self, obj):
        rows = self._household_rows(obj)
        result = []
        for hh in rows:
            customer = hh.customer_id
            result.append({
                "unique_id": hh.unique_id,
                "sequence": hh.sequence,
                "status": hh.status,
                "status_reason": hh.status_reason,
                "is_collected": hh.is_collected,
                "collected_at": hh.collected_at.isoformat() if hh.collected_at else None,
                "collected_weight_kg": (
                    str(hh.collected_weight_kg)
                    if hh.collected_weight_kg is not None else None
                ),
                "customer": self._customer_brief(customer),
            })
        return result

    @staticmethod
    def _customer_brief(customer):
        if customer is None:
            return None

        def _num(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        address = ", ".join(
            part for part in [
                getattr(customer, "building_no", None),
                getattr(customer, "street", None),
                getattr(customer, "area", None),
            ] if part
        )
        return {
            "unique_id": customer.unique_id,
            "name": customer.customer_name,
            "contact_no": getattr(customer, "contact_no", None),
            "address": address or None,
            "latitude": _num(getattr(customer, "latitude", None)),
            "longitude": _num(getattr(customer, "longitude", None)),
        }

    def get_collection_points(self, obj):
        children = (
            obj.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id", "bin_id")
            .order_by("sequence")
        )
        return TripCollectionPointSerializer(
            children, many=True, context=self.context
        ).data

    def get_distance_meters(self, obj):
        return self._route_for_assignment(obj)["distance"]

    def get_duration_seconds(self, obj):
        return self._route_for_assignment(obj)["duration"]

    def get_route_geojson(self, obj):
        return self._route_for_assignment(obj)["geometry"]

    def get_vehicle_start(self, obj):
        return self._route_for_assignment(obj)["vehicle_start"]

    def _route_for_assignment(self, obj):
        local_cache = getattr(self, "_route_cache", None)
        if local_cache is None:
            local_cache = {}
            self._route_cache = local_cache
        if obj.unique_id in local_cache:
            return local_cache[obj.unique_id]

        stops = list(
            obj.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id")
            .order_by("sequence")
        )
        route_input = []
        for stop in stops:
            cp = stop.collection_point_id
            if not cp or cp.latitude is None or cp.longitude is None:
                continue
            route_input.append({
                "id": stop.unique_id,
                "location": [float(cp.longitude), float(cp.latitude)],
            })

        vehicle_start = self._latest_vehicle_start(obj)
        route_signature = "|".join(
            [
                obj.unique_id,
                str(vehicle_start),
                *[
                    f"{stop.unique_id}:{stop.sequence}:"
                    f"{getattr(stop.collection_point_id, 'latitude', None)}:"
                    f"{getattr(stop.collection_point_id, 'longitude', None)}"
                    for stop in stops
                ],
            ]
        )
        cache_key = (
            "operator-my-trip-route:"
            f"{hashlib.sha1(route_signature.encode()).hexdigest()}"
        )
        route = cache.get(cache_key)
        if route is None:
            route = route_stops(route_input, vehicle_start)
            cache.set(cache_key, route, timeout=300)

        local_cache[obj.unique_id] = route
        return route

    def _latest_vehicle_start(self, assignment):
        latest_event = (
            BinCollectionEvent.objects
            .filter(trip_assignment_id=assignment)
            .exclude(driver_latitude=None)
            .exclude(driver_longitude=None)
            .order_by("-created_at")
            .first()
        )
        if not latest_event:
            return None
        return [
            float(latest_event.driver_longitude),
            float(latest_event.driver_latitude),
        ]
