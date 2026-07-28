from decimal import Decimal, ROUND_HALF_UP

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.core_modules.attendance.daily_attendance_reg import DailyAttendanceReg
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.secondary_bin_collection_event import (
    BinCollectionEvent,
)
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_requester_scope,
    filter_staff_queryset_by_requester_scope,
)


TWO = Decimal("0.01")


LOCAL_BODY_MODELS = {
    "corporation_id": (Corporation, "corporation_name", "Corporation"),
    "municipality_id": (Municipality, "municipality_name", "Municipality"),
    "town_panchayat_id": (TownPanchayat, "town_panchayat_name", "Town Panchayat"),
    "panchayat_union_id": (PanchayatUnion, "union_name", "Panchayat Union"),
    "panchayat_id": (Panchayat, "panchayat_name", "Panchayat"),
}

FILTER_SCOPE_FIELD_MAPS = {
    "state": {"state_id": "unique_id"},
    "district": {"district_id": "unique_id", "state_id": "state_id_id"},
    "area_type": {
        "area_type_id": "unique_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
    "corporation_id": {
        "corporation_id": "unique_id",
        "area_type_id": "area_type_id_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
    "municipality_id": {
        "municipality_id": "unique_id",
        "area_type_id": "area_type_id_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
    "town_panchayat_id": {
        "town_panchayat_id": "unique_id",
        "area_type_id": "area_type_id_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
    "panchayat_union_id": {
        "panchayat_union_id": "unique_id",
        "area_type_id": "area_type_id_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
    "panchayat_id": {
        "panchayat_id": "unique_id",
        "area_type_id": "area_type_id_id",
        "district_id": "district_id_id",
        "state_id": "state_id_id",
    },
}


def _round(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _model_has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _active(qs):
    model = qs.model
    if _model_has_field(model, "is_deleted"):
        qs = qs.filter(is_deleted=False)
    if _model_has_field(model, "is_active"):
        qs = qs.filter(is_active=True)
    return qs


class DashboardSummaryViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        params = self._clean_params(request.query_params)
        date_str = params.pop("date", None)
        # Default to today when no date filter is picked, matching the
        # "Today's ..." framing of these cards — without this, the
        # date-scoped summaries (households/attendance/waste/bins/trip
        # performance) aggregated across the whole seeded history instead
        # of a single day, producing nonsensical figures like "126/43
        # households (293%)" once more than one day of data exists.
        target_date = timezone.localdate()
        if date_str:
            try:
                parsed = parse_date(date_str)
                if parsed is not None:
                    target_date = parsed
            except (ValueError, TypeError):
                pass

        return Response(
            {
                "filters": self._filter_options(params),
                "summary": {
                    "households": self._household_summary(params, target_date),
                    "attendance": self._attendance_summary(params, target_date),
                    "waste": self._waste_summary(params, target_date),
                    "bins": self._bin_summary(params, target_date),
                    "vehicles": self._vehicle_summary(params),
                    "grievances": self._grievance_summary(params),
                    "masters": self._master_summary(params),
                },
                "recent_grievances": self._recent_grievances(params),
                "critical_alerts": self._critical_alerts(params),
                "vehicle_performance": self._vehicle_performance(params, target_date),
                "trip_performance": self._trip_performance(params, target_date),
                "team_performance": self._team_performance(params, target_date),
                "ward_performance": self._ward_performance(params, target_date),
                "collection_progress": self._collection_progress(params, target_date),
                "vehicle_status_detail": self._vehicle_status_detail(params),
                "as_of": timezone.now().isoformat(),
            }
        )

    def _clean_params(self, query_params):
        allowed = {
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
            "ward_id",
            "local_body_type",
            "date",
        }
        return {
            key: str(query_params.get(key)).strip()
            for key in allowed
            if str(query_params.get(key, "")).strip()
        }

    def _apply_geo(self, qs, params, include_ward=True):
        for key, value in params.items():
            if key == "local_body_type":
                if value in LOCAL_BODY_MODELS:
                    field_name = value.removesuffix("_id")
                    if _model_has_field(qs.model, field_name):
                        qs = qs.filter(**{f"{value}__isnull": False})
                continue
            if key == "ward_id" and not include_ward:
                continue
            if _model_has_field(qs.model, key):
                qs = qs.filter(**{key: value})
        return qs

    def _apply_scope(self, qs, field_map=None, include_ward=True):
        if qs.model is StaffcreationOfficeDetails:
            return filter_staff_queryset_by_requester_scope(qs, self.request.user)

        if field_map is None:
            field_map = {
                "panchayat_id": "panchayat_id",
                "panchayat_union_id": "panchayat_union_id",
                "town_panchayat_id": "town_panchayat_id",
                "municipality_id": "municipality_id",
                "corporation_id": "corporation_id",
                "district_id": "district_id",
                "state_id": "state_id",
            }

        if not include_ward:
            field_map = dict(field_map)
            field_map.pop("ward", None)
            field_map.pop("ward_id", None)

        return filter_flat_geo_queryset_by_requester_scope(qs, self.request.user, field_map=field_map)

    def _apply_dashboard_geo(self, qs, params, include_ward=True, field_map=None):
        return self._apply_scope(self._apply_geo(qs, params, include_ward=include_ward), field_map, include_ward)

    def _filter_options(self, params):
        state_qs = self._apply_scope(
            _active(State.objects.all()).order_by("name"),
            FILTER_SCOPE_FIELD_MAPS["state"],
        )
        district_qs = self._apply_scope(
            _active(District.objects.all()).order_by("name"),
            FILTER_SCOPE_FIELD_MAPS["district"],
        )
        area_type_qs = self._apply_scope(
            _active(AreaType.objects.all()).order_by("name"),
            FILTER_SCOPE_FIELD_MAPS["area_type"],
        )
        ward_qs = self._apply_scope(_active(Ward.objects.all()).order_by("ward_name"))

        if params.get("state_id"):
            district_qs = district_qs.filter(state_id=params["state_id"])
            area_type_qs = area_type_qs.filter(state_id=params["state_id"])
            ward_qs = ward_qs.filter(state_id=params["state_id"])
        if params.get("district_id"):
            area_type_qs = area_type_qs.filter(district_id=params["district_id"])
            ward_qs = ward_qs.filter(district_id=params["district_id"])
        if params.get("area_type_id"):
            ward_qs = ward_qs.filter(area_type_id=params["area_type_id"])

        local_bodies = []
        for key, (model, name_field, label) in LOCAL_BODY_MODELS.items():
            if params.get("local_body_type") and params["local_body_type"] != key:
                continue
            qs = self._apply_scope(
                _active(model.objects.all()).order_by(name_field),
                FILTER_SCOPE_FIELD_MAPS[key],
            )
            if params.get("state_id"):
                qs = qs.filter(state_id=params["state_id"])
            if params.get("district_id"):
                qs = qs.filter(district_id=params["district_id"])
            if params.get("area_type_id"):
                qs = qs.filter(area_type_id=params["area_type_id"])
            for row in qs[:500]:
                local_bodies.append(
                    {
                        "id": row.unique_id,
                        "name": getattr(row, name_field, row.unique_id),
                        "type": key,
                        "type_label": label,
                    }
                )

        for key in LOCAL_BODY_MODELS:
            if params.get(key):
                ward_qs = ward_qs.filter(**{key: params[key]})

        return {
            "states": [{"id": r.unique_id, "name": r.name} for r in state_qs[:100]],
            "districts": [{"id": r.unique_id, "name": r.name} for r in district_qs[:500]],
            "area_types": [{"id": r.unique_id, "name": r.name} for r in area_type_qs[:200]],
            "local_bodies": local_bodies,
            "wards": [{"id": r.unique_id, "name": r.ward_name} for r in ward_qs[:1000]],
        }

    def _household_summary(self, params, target_date=None):
        customers = self._apply_dashboard_geo(_active(CustomerCreation.objects.all()), params)
        stops_qs = self._apply_dashboard_geo(
            DailyTripHouseholdCollection.objects.filter(is_deleted=False),
            params,
        )
        if target_date:
            # DailyTripHouseholdCollection has no date field of its own —
            # `created_at` is just when the row was inserted (e.g. all at
            # once during seeding), not the day it represents. The real
            # business date lives on the parent assignment.
            stops_qs = stops_qs.filter(trip_assignment_id__trip_date=target_date)
        stops = stops_qs

        status_counts = stops.aggregate(
            collected=Count("unique_id", filter=Q(status=DailyTripHouseholdCollection.STATUS_COLLECTED)),
            not_available=Count("unique_id", filter=Q(status=DailyTripHouseholdCollection.STATUS_MISSED)),
            not_collected=Count(
                "unique_id",
                filter=Q(
                    status__in=[
                        DailyTripHouseholdCollection.STATUS_PENDING,
                        DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
                        DailyTripHouseholdCollection.STATUS_SKIPPED,
                    ]
                ),
            ),
        )
        return {
            "total_customers": customers.count(),
            "collected": status_counts["collected"] or 0,
            "not_available": status_counts["not_available"] or 0,
            "not_collected": status_counts["not_collected"] or 0,
        }

    def _attendance_summary(self, params, target_date=None):
        staff = self._apply_dashboard_geo(
            StaffcreationOfficeDetails.objects.filter(is_deleted=False, active_status=True),
            params,
            include_ward=False,
        )
        attendance_filter = Q(staff__in=staff, punch_type="IN")
        if target_date:
            attendance_filter &= Q(recognition_date=target_date)
        attendance = DailyAttendanceReg.objects.filter(attendance_filter)
        present = attendance.values("staff_id").distinct().count()
        total = staff.count()
        return {
            "total": total,
            "present": present,
            "absent": max(total - present, 0),
            "leave": 0,
        }

    def _waste_summary(self, params, target_date=None):
        qs = self._apply_dashboard_geo(
            WasteCollection.objects.filter(is_deleted=False),
            params,
        )
        if target_date:
            qs = qs.filter(collection_date=target_date)
        totals = qs.aggregate(
            total_kg=Sum("total_quantity"),
            wet_kg=Sum("wet_waste"),
            dry_kg=Sum("dry_waste"),
            mixed_kg=Sum("mixed_waste"),
            sanitary_kg=Sum("sanitary_waste"),
        )
        wet = _round(totals["wet_kg"])
        dry = _round(totals["dry_kg"])
        mixed = _round(totals["mixed_kg"])
        sanitary = _round(totals["sanitary_kg"])
        total = _round(totals["total_kg"])
        other = mixed + sanitary
        return {
            "total_kg": float(total),
            "total_tons": float(_round(total / Decimal("1000"))),
            "wet_kg": float(wet),
            "dry_kg": float(dry),
            "other_kg": float(other),
            "wet_tons": float(_round(wet / Decimal("1000"))),
            "dry_tons": float(_round(dry / Decimal("1000"))),
            "other_tons": float(_round(other / Decimal("1000"))),
            "collections": qs.count(),
        }

    def _bin_summary(self, params, target_date=None):
        bins = self._apply_dashboard_geo(_active(Bins.objects.all()), params)
        events = self._apply_dashboard_geo(
            BinCollectionEvent.objects.filter(is_deleted=False),
            params,
        )
        if target_date:
            events = events.filter(collection_date=target_date)
        collected_bins = events.filter(
            status=BinCollectionEvent.STATUS_COLLECTED
        ).values("bin_id").distinct().count()
        total = bins.count()
        return {
            "total": total,
            "collected": collected_bins,
            "not_collected": max(total - collected_bins, 0),
        }

    def _vehicle_summary(self, params):
        vehicles = self._apply_dashboard_geo(_active(VehicleCreation.objects.all()), params, include_ward=False)
        total = vehicles.count()
        active = vehicles.filter(is_active=True).count()
        return {
            "total": total,
            "active": active,
            "inactive": max(total - active, 0),
        }

    def _grievance_summary(self, params):
        qs = self._apply_dashboard_geo(
            ComplaintTicket.objects.filter(is_deleted=False),
            params,
            include_ward=False,
        )
        resolved_q = Q(status__is_final=True) | Q(status__status_code__icontains="resolved") | Q(
            status__status_name__icontains="resolved"
        )
        in_progress_q = (
            Q(status__status_code__icontains="progress")
            | Q(status__status_name__icontains="progress")
            | Q(status__status_code__icontains="assigned")
            | Q(status__status_name__icontains="assigned")
        )
        counts = qs.aggregate(
            total=Count("unique_id"),
            resolved=Count("unique_id", filter=resolved_q),
            in_progress=Count("unique_id", filter=in_progress_q),
        )
        total = counts["total"] or 0
        resolved = counts["resolved"] or 0
        in_progress = counts["in_progress"] or 0
        return {
            "total": total,
            "open": max(total - resolved - in_progress, 0),
            "in_progress": in_progress,
            "resolved": resolved,
        }

    def _master_summary(self, params):
        return {
            "states": self._apply_scope(
                _active(State.objects.all()),
                FILTER_SCOPE_FIELD_MAPS["state"],
                include_ward=False,
            ).count(),
            "districts": self._apply_dashboard_geo(
                _active(District.objects.all()),
                params,
                include_ward=False,
                field_map=FILTER_SCOPE_FIELD_MAPS["district"],
            ).count(),
            "area_types": self._apply_dashboard_geo(
                _active(AreaType.objects.all()),
                params,
                include_ward=False,
                field_map=FILTER_SCOPE_FIELD_MAPS["area_type"],
            ).count(),
            "local_bodies": sum(
                self._apply_dashboard_geo(
                    _active(model.objects.all()),
                    params,
                    include_ward=False,
                    field_map=FILTER_SCOPE_FIELD_MAPS[key],
                ).count()
                for key, (model, _, _) in LOCAL_BODY_MODELS.items()
            ),
            "wards": self._apply_dashboard_geo(_active(Ward.objects.all()), params).count(),
        }

    def _vehicle_performance(self, params, target_date=None):
        _qs = self._apply_dashboard_geo(
            VehicleCreation.objects.select_related("vehicle_type").filter(
                is_deleted=False,
            ),
            params,
            include_ward=False,
        )[:20]
        vehicles = list(_qs)
        v_ids = [v.unique_id for v in vehicles]

        trip_agg = (
            DailyTripAssignment.objects.filter(
                vehicle_id__in=v_ids,
                is_deleted=False,
            )
        )
        if target_date:
            trip_agg = trip_agg.filter(trip_date=target_date)
        trip_agg = trip_agg.values("vehicle_id").annotate(
            trip_count=Count("unique_id"),
        )
        trip_map = {r["vehicle_id"]: r["trip_count"] for r in trip_agg}

        waste_agg = (
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id__vehicle_id__in=v_ids,
                is_collected=True,
            )
        )
        if target_date:
            # Same fix as _household_summary — filter on the assignment's
            # real trip_date, not the row's insert timestamp.
            waste_agg = waste_agg.filter(trip_assignment_id__trip_date=target_date)
        waste_agg = waste_agg.values(
            "trip_assignment_id__vehicle_id"
        ).annotate(
            total_kg=Sum("collected_weight_kg"),
            stop_count=Count("unique_id"),
        )
        waste_map = {
            r["trip_assignment_id__vehicle_id"]: r
            for r in waste_agg
        }

        return [
            {
                "registration_no": v.vehicle_no,
                "vehicle_type": (
                    v.vehicle_type.vehicleType
                    if getattr(v, "vehicle_type_id", None) and v.vehicle_type
                    else ""
                ),
                "ward_name": "",
                "trips": trip_map.get(v.unique_id, 0),
                "waste_tons": round(
                    float(
                        (waste_map.get(v.unique_id, {})).get("total_kg") or 0
                    ) / 1000,
                    2,
                ),
                "capacity_pct": min(
                    round(
                        float(
                            (waste_map.get(v.unique_id, {})).get("total_kg") or 0
                        )
                        / max(float(v.capacity or 1), 1)
                        * 100,
                    ),
                    100,
                ),
                "status": "Active" if v.is_active else "Inactive",
            }
            for v in vehicles
        ]

    def _trip_performance(self, params, target_date=None):
        qs = DailyTripAssignment.objects.filter(is_deleted=False).select_related(
            "vehicle_id", "trip_plan_id"
        )
        qs = self._apply_dashboard_geo(qs, params)
        if target_date:
            qs = qs.filter(trip_date=target_date)
        qs = qs.order_by("-created_at")[:10]

        assignment_ids = [a.unique_id for a in qs]
        stop_counts = dict(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id__in=assignment_ids,
            )
            .values("trip_assignment_id")
            .annotate(cnt=Count("unique_id"))
            .values_list("trip_assignment_id", "cnt")
        )
        weight_agg = dict(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id__in=assignment_ids,
                is_collected=True,
            )
            .values("trip_assignment_id")
            .annotate(
                total_kg=Sum("collected_weight_kg"),
            )
            .values_list("trip_assignment_id", "total_kg")
        )

        return [
            {
                "trip_id": (
                    a.trip_plan_id.display_code
                    if a.trip_plan_id
                    else a.unique_id
                ),
                "vehicle_no": (
                    a.vehicle_id.vehicle_no if a.vehicle_id else ""
                ),
                "ward_name": "",
                "start_time": (
                    a.actual_start_time.strftime("%I:%M %p")
                    if a.actual_start_time
                    else (
                        a.scheduled_time.strftime("%I:%M %p")
                        if a.scheduled_time
                        else ""
                    )
                ),
                "stops": stop_counts.get(a.unique_id, 0),
                "weight_tons": round(
                    float(weight_agg.get(a.unique_id) or 0) / 1000, 2
                ),
                "status": a.status,
            }
            for a in qs
        ]

    def _team_performance(self, params, target_date=None):
        qs = DailyTripAssignment.objects.filter(
            is_deleted=False,
            staff_template_id__isnull=False,
        ).select_related("staff_template_id", "vehicle_id")
        qs = self._apply_dashboard_geo(qs, params)
        if target_date:
            qs = qs.filter(trip_date=target_date)

        team_agg = (
            qs.values("staff_template_id")
            .annotate(
                trip_count=Count("unique_id"),
            )
        )

        templates = StaffTemplate.objects.filter(
            unique_id__in=[r["staff_template_id"] for r in team_agg],
        )
        template_map = {t.unique_id: t for t in templates}

        assignment_ids = list(qs.values_list("unique_id", flat=True))
        waste_agg = {}
        if assignment_ids:
            waste_rows = (
                DailyTripHouseholdCollection.objects.filter(
                    trip_assignment_id__in=assignment_ids,
                    is_collected=True,
                )
                .values("trip_assignment_id")
                .annotate(
                    total_kg=Sum("collected_weight_kg"),
                )
            )
            for r in waste_rows:
                ta_id = r["trip_assignment_id"]
                waste_agg[ta_id] = float(r["total_kg"] or 0)

        result = []
        for row in team_agg:
            tmpl = template_map.get(row["staff_template_id"])
            if not tmpl:
                continue
            staff_count = 2
            if tmpl.extra_operator_id:
                try:
                    staff_count += len(tmpl.extra_operator_id)
                except Exception:
                    pass
            result.append({
                "team_name": tmpl.display_code,
                "ward_name": "",
                "attendance_present": row["trip_count"],
                "attendance_total": staff_count,
                "trips": row["trip_count"],
                "waste_tons": round(
                    sum(
                        waste_agg.get(aid, 0)
                        for aid in qs.filter(
                            staff_template_id=row["staff_template_id"]
                        ).values_list("unique_id", flat=True)
                    )
                    / 1000,
                    2,
                ),
                "score": min(
                    round(
                        (row["trip_count"] / max(staff_count, 1)) * 20
                    ),
                    100,
                ),
            })
        return sorted(result, key=lambda x: x["score"], reverse=True)[:10]

    def _ward_performance(self, params, target_date=None):
        _ward_qs = self._apply_dashboard_geo(
            Ward.objects.filter(is_deleted=False), params
        ).select_related("district")[:50]
        ward_list = list(_ward_qs)
        ward_ids = [w.unique_id for w in ward_list]

        collection_qs = DailyTripHouseholdCollection.objects.filter(
            customer_id__ward__in=ward_ids,
            is_deleted=False,
        )
        if target_date:
            # Same fix as _household_summary — filter on the assignment's
            # real trip_date, not the row's insert timestamp.
            collection_qs = collection_qs.filter(trip_assignment_id__trip_date=target_date)

        agg = (
            collection_qs.values("customer_id__ward")
            .annotate(
                collected=Count("customer_id", filter=Q(is_collected=True), distinct=True),
                missed=Count(
                    "unique_id",
                    filter=Q(status=DailyTripHouseholdCollection.STATUS_MISSED),
                ),
                not_collected=Count(
                    "unique_id",
                    filter=Q(
                        status__in=[
                            DailyTripHouseholdCollection.STATUS_NOT_COLLECTED,
                            DailyTripHouseholdCollection.STATUS_SKIPPED,
                        ]
                    ),
                ),
                household_kg=Sum("collected_weight_kg"),
            )
        )
        ward_data = {r["customer_id__ward"]: r for r in agg}

        customer_agg = (
            self._apply_dashboard_geo(_active(CustomerCreation.objects.filter(ward__in=ward_ids)), params)
            .values("ward")
            .annotate(total_customers=Count("unique_id"))
        )
        customer_data = {r["ward"]: r for r in customer_agg}

        bin_master_agg = (
            self._apply_dashboard_geo(_active(Bins.objects.filter(ward__in=ward_ids)), params)
            .values("ward")
            .annotate(total_bins=Count("unique_id"))
        )
        bin_master_data = {r["ward"]: r for r in bin_master_agg}

        # Bin (secondary collection point) stats per ward — BinCollectionEvent
        # carries its own `ward` FK directly (set by the seeder / ScanBinViewSet),
        # so this is a straight aggregate, no join through customers needed.
        bin_qs = BinCollectionEvent.objects.filter(ward__in=ward_ids, is_deleted=False)
        if target_date:
            bin_qs = bin_qs.filter(collection_date=target_date)
        bin_agg = bin_qs.values("ward").annotate(
            bin_kg=Sum("collected_weight_kg"),
            bin_collected=Count("bin_id", filter=Q(status=BinCollectionEvent.STATUS_COLLECTED), distinct=True),
        )
        bin_data = {r["ward"]: r for r in bin_agg}

        # Expected capacity, split by collection type — the combined
        # max_vehicle_capacity_kg of whichever bin/household TripPlan serves
        # this specific ward (TripPlan.wards is set to exactly one ward per
        # plan — see TripPlanSeeder), so each ward's card can show separate
        # household and bin current/target ratios.
        plan_agg = (
            TripPlan.objects.filter(wards__in=ward_ids, is_deleted=False)
            .values("wards__unique_id", "collection_type")
            .annotate(target_kg=Sum("max_vehicle_capacity_kg"))
        )
        household_target = {}
        bin_target = {}
        for r in plan_agg:
            ward_id = r["wards__unique_id"]
            if r["collection_type"] == TripPlan.COLLECTION_TYPE_HOUSEHOLD:
                household_target[ward_id] = float(r["target_kg"] or 0)
            elif r["collection_type"] == TripPlan.COLLECTION_TYPE_BIN:
                bin_target[ward_id] = float(r["target_kg"] or 0)

        # Trip/driver/operator details for the hover tooltip — a ward
        # typically has 2 DailyTripAssignments (its bin route + household
        # route). Deliberately NOT filtered by target_date: "today" has no
        # seeded history (it's reserved for the live driver_user/scheduler
        # demo trip — see DailyTripAssignmentSeeder), so restricting the
        # tooltip to the same date as the weight/completion cards would
        # leave it empty by default on every page load. Instead, always
        # surface the MOST RECENT assignment per (ward, collection type),
        # regardless of which date the rest of the card is showing.
        assignment_rows = (
            DailyTripAssignment.objects.filter(wards__in=ward_ids, is_deleted=False)
            .order_by("-trip_date", "-scheduled_time")
            .values(
                "unique_id",
                "wards__unique_id",
                "trip_plan_id__collection_type",
                "trip_date",
                "actual_start_time",
                "scheduled_time",
                "vehicle_id__vehicle_no",
                "staff_template_id__driver_id__employee_name",
                "staff_template_id__operator_id__employee_name",
            )
        )

        trips_by_ward = {}
        seen_ward_types = set()
        for r in assignment_rows:
            ward_id = r["wards__unique_id"]
            collection_type = r["trip_plan_id__collection_type"]
            if not ward_id:
                continue
            key = (ward_id, collection_type)
            if key in seen_ward_types:
                # Already recorded the most recent trip for this ward +
                # collection type (rows are ordered newest-first).
                continue
            seen_ward_types.add(key)
            trip_time = r["actual_start_time"] or r["scheduled_time"]
            trips_by_ward.setdefault(ward_id, []).append({
                "trip_id": r["unique_id"],
                "collection_type": collection_type,
                "driver_name": r["staff_template_id__driver_id__employee_name"] or "-",
                "operator_name": r["staff_template_id__operator_id__employee_name"] or "-",
                "vehicle_no": r["vehicle_id__vehicle_no"] or "-",
                "trip_date": r["trip_date"].isoformat() if r["trip_date"] else None,
                "trip_time": trip_time.strftime("%H:%M") if trip_time else None,
            })

        result = []
        for w in ward_list:
            row = ward_data.get(w.unique_id, {})
            customer_row = customer_data.get(w.unique_id, {})
            bin_master_row = bin_master_data.get(w.unique_id, {})
            brow = bin_data.get(w.unique_id, {})
            household_kg = round(float(row.get("household_kg") or 0), 2)
            bin_kg = round(float(brow.get("bin_kg") or 0), 2)
            household_target_kg = round(household_target.get(w.unique_id, 0), 2)
            bin_target_kg = round(bin_target.get(w.unique_id, 0), 2)
            household_total = customer_row.get("total_customers", 0)
            bin_total = bin_master_row.get("total_bins", 0)
            result.append({
                "ward_id": w.unique_id,
                "ward_name": w.ward_name,
                "district_name": w.district.name if w.district_id else "",
                "trips": trips_by_ward.get(w.unique_id, []),
                "household_current_kg": household_kg,
                "household_target_kg": household_target_kg,
                "bin_current_kg": bin_kg,
                "bin_target_kg": bin_target_kg,
                "current_weight_kg": round(household_kg + bin_kg, 2),
                "overall_weight_kg": round(household_target_kg + bin_target_kg, 2),
                "waste_tons": round((household_kg + bin_kg) / 1000, 2),
                "status": (
                    "delayed"
                    if row.get("not_collected", 0) > row.get("collected", 0)
                    else "no_vehicle"
                    if household_total == 0 and bin_total == 0
                    else "normal"
                ),
                "households_collected": row.get("collected", 0),
                "households_total": household_total,
                "bins_collected": brow.get("bin_collected", 0),
                "bins_total": bin_total,
                "completion_pct": round(
                    (row.get("collected", 0) / max(household_total, 1)) * 100,
                    1,
                ),
            })
        return result

    def _collection_progress(self, params, target_date=None):
        qs = WasteCollection.objects.filter(is_deleted=False)
        qs = self._apply_dashboard_geo(qs, params)

        today = target_date or timezone.localdate()
        labels = []
        for i in range(31):
            d = today - timedelta(days=30 - i)
            labels.append(d.isoformat())

        daily = {}
        for d in labels:
            daily[d] = {"count": 0, "total_kg": 0}

        day_agg = (
            qs.filter(collection_date__gte=today - timedelta(days=30))
            .values("collection_date")
            .annotate(
                cnt=Count("unique_id"),
                total_kg=Sum("total_quantity"),
            )
        )
        for r in day_agg:
            key = str(r["collection_date"])
            if key in daily:
                daily[key]["count"] = r["cnt"] or 0
                daily[key]["total_kg"] = float(r["total_kg"] or 0)

        max_val = max(
            (v["count"] for v in daily.values()), default=1
        )
        return [
            {
                "label": d.split("-")[2],
                "value": daily[d]["count"],
                "pct": round(
                    (daily[d]["count"] / (max_val or 1)) * 100, 1
                ),
                "total_kg": daily[d]["total_kg"],
            }
            for d in sorted(daily.keys())
        ]

    def _vehicle_status_detail(self, params):
        vehicles = self._apply_dashboard_geo(
            VehicleCreation.objects.filter(is_deleted=False),
            params,
            include_ward=False,
        )
        total = vehicles.count()
        active = vehicles.filter(is_active=True).count()
        inactive = max(total - active, 0)
        today = timezone.localdate()
        vehicles_with_trips_today = set(
            DailyTripAssignment.objects.filter(
                vehicle_id__in=vehicles.values("unique_id"),
                trip_date=today,
                is_deleted=False,
            ).values_list("vehicle_id", flat=True)
        )
        idle_count = 0
        for v in vehicles.iterator():
            if not v.is_active:
                continue
            if v.unique_id not in vehicles_with_trips_today:
                idle_count += 1
        breakdowns = VehicleBreakdown.objects.filter(
            is_deleted=False,
            status=VehicleBreakdown.STATUS_REPORTED,
        )
        breakdowns = self._apply_breakdown_geo(breakdowns, params)
        breakdown_count = breakdowns.count()
        return {
            "idle": idle_count,
            "breakdown": breakdown_count,
            "offline_gps": max(round(total * 0.06), 0),
        }

    def _apply_breakdown_geo(self, qs, params):
        prefix = "trip_assignment_id__"
        for key, value in params.items():
            if key == "local_body_type":
                if value in LOCAL_BODY_MODELS:
                    qs = qs.filter(**{f"{prefix}{value}__isnull": False})
                continue
            if key == "ward_id":
                continue
            if key in {
                "state_id",
                "district_id",
                "area_type_id",
                *LOCAL_BODY_MODELS.keys(),
            }:
                qs = qs.filter(**{f"{prefix}{key}": value})
        return filter_flat_geo_queryset_by_requester_scope(
            qs,
            self.request.user,
            field_map={
                field: f"{prefix}{field}"
                for field in (
                    "state_id",
                    "district_id",
                    "area_type_id",
                    "corporation_id",
                    "municipality_id",
                    "town_panchayat_id",
                    "panchayat_union_id",
                    "panchayat_id",
                )
            },
        )

    def _critical_alerts(self, params):
        complaints = self._apply_dashboard_geo(
            ComplaintTicket.objects.filter(is_deleted=False)
            .exclude(status__is_final=True)
            .select_related(
                "status",
                "priority",
                "category",
                "subcategory",
                "source",
                "assigned_team",
                "assigned_staff",
                "district",
                "corporation",
                "municipality",
                "town_panchayat",
                "panchayat_union",
                "panchayat",
            )
            .prefetch_related("extra_details")
            .order_by("-created"),
            params,
            include_ward=False,
        )[:10]
        breakdowns = self._apply_breakdown_geo(
            VehicleBreakdown.objects.filter(
                is_deleted=False,
            )
            .exclude(status=VehicleBreakdown.STATUS_REJECTED)
            .select_related(
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "breakdown_vehicle_id",
                "replacement_driver_id",
                "replacement_operator_id",
                "replacement_vehicle_id",
                "trip_assignment_id__staff_template_id",
                "trip_assignment_id__staff_template_id__driver_id",
                "trip_assignment_id__staff_template_id__operator_id",
                "trip_assignment_id__alt_staff_template_id",
                "trip_assignment_id__alt_staff_template_id__driver_id",
                "trip_assignment_id__alt_staff_template_id__operator_id",
            )
            .order_by("-created_at"),
            params,
        )[:10]

        alerts = []
        for row in complaints:
            context = {
                detail.field_key: detail.field_value
                for detail in row.extra_details.all()
                if not detail.is_deleted
            }
            _, _, local_body_name = row.local_body
            priority = getattr(row.priority, "priority_name", "") or ""
            source_code = getattr(row.source, "source_code", "") or ""
            alerts.append(
                {
                    "id": row.ticket_no or row.unique_id,
                    "kind": "grievance",
                    "title": row.title or getattr(row.category, "category_name", "") or "Complaint",
                    "description": row.description or "",
                    "status": getattr(row.status, "status_name", ""),
                    "severity": (
                        "critical"
                        if "critical" in priority.lower() or "high" in priority.lower()
                        else "warning"
                    ),
                    "created": row.created.isoformat() if row.created else None,
                    "updated": row.updated.isoformat() if row.updated else None,
                    "priority": priority,
                    "category": getattr(row.category, "category_name", "") or "",
                    "subcategory": getattr(row.subcategory, "subcategory_name", "") or "",
                    "source": "Public Grievance" if source_code == "PUBLIC_GRIEVANCE" else source_code.replace("_", " ").title(),
                    "incident_type": context.get("incident_type") or (
                        "public" if source_code == "PUBLIC_GRIEVANCE" else "other"
                    ),
                    "assigned_to": (
                        getattr(row.assigned_staff, "employee_name", "")
                        or getattr(row.assigned_team, "team_name", "")
                        or ""
                    ),
                    "location": " · ".join(
                        value
                        for value in (
                            row.location_text or "",
                            local_body_name or "",
                            getattr(row.district, "name", "") or "",
                        )
                        if value
                    ),
                    "trip": context.get("trip_reference") or "",
                    "vehicle": context.get("vehicle_reference") or "",
                    "driver": context.get("driver_reference") or "",
                    "operator": context.get("operator_reference") or "",
                    "remarks": context.get("other_reference") or "",
                }
            )
        for row in breakdowns:
            assignment = row.trip_assignment_id
            trip_plan = getattr(assignment, "trip_plan_id", None)
            template = assignment.alt_staff_template_id or assignment.staff_template_id
            alerts.append(
                {
                    "id": row.unique_id,
                    "kind": "vehicle_breakdown",
                    "title": f"{row.get_breakdown_reason_display()} · {row.breakdown_vehicle_id.vehicle_no}",
                    "status": row.get_status_display(),
                    "severity": "critical" if row.status == VehicleBreakdown.STATUS_REPORTED else "warning",
                    "created": row.created_at.isoformat() if row.created_at else None,
                    "updated": row.updated_at.isoformat() if row.updated_at else None,
                    "priority": "Critical" if row.status == VehicleBreakdown.STATUS_REPORTED else "High",
                    "category": "Vehicle Breakdown",
                    "subcategory": row.get_breakdown_reason_display(),
                    "source": "Operations",
                    "incident_type": "vehicle",
                    "assigned_to": "",
                    "location": row.breakdown_location or "",
                    "trip": getattr(trip_plan, "display_code", "") or assignment.unique_id,
                    "vehicle": row.breakdown_vehicle_id.vehicle_no,
                    "replacement_vehicle": getattr(row.replacement_vehicle_id, "vehicle_no", "") or "",
                    "driver": getattr(getattr(template, "driver_id", None), "employee_name", "") or "",
                    "operator": getattr(getattr(template, "operator_id", None), "employee_name", "") or "",
                    "replacement_driver": getattr(row.replacement_driver_id, "employee_name", "") or "",
                    "replacement_operator": getattr(row.replacement_operator_id, "employee_name", "") or "",
                    "trip_date": assignment.trip_date.isoformat() if assignment.trip_date else "",
                    "scheduled_time": str(assignment.scheduled_time) if assignment.scheduled_time else "",
                    "breakdown_time": str(row.breakdown_time) if row.breakdown_time else "",
                    "approval_status": row.get_approval_status_display(),
                    "collected_weight_kg": str(row.collected_weight_before_breakdown_kg or ""),
                    "description": row.breakdown_remarks or row.get_breakdown_reason_display(),
                    "remarks": row.breakdown_remarks or "",
                }
            )
        alerts.sort(key=lambda item: item.get("created") or "", reverse=True)
        return alerts[:10]

    def _recent_grievances(self, params):
        qs = self._apply_dashboard_geo(
            ComplaintTicket.objects.filter(is_deleted=False)
            .select_related("status", "priority", "category")
            .order_by("-created"),
            params,
            include_ward=False,
        )[:10]
        return [
            {
                "id": row.ticket_no or row.unique_id,
                "title": row.title or getattr(row.category, "category_name", "") or "Complaint",
                "status": getattr(row.status, "status_name", ""),
                "priority": getattr(row.priority, "priority_name", ""),
                "created": row.created.isoformat() if row.created else None,
            }
            for row in qs
        ]
