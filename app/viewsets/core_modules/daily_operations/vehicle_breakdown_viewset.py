from django.db.models import Q
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.models.core_modules.daily_operations.vehicle_breakdown import (
    VehicleBreakdown,
    VehicleBreakdownPhoto,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownSerializer,
    VehicleBreakdownVerifySerializer,
    VehicleBreakdownRejectSerializer,
)
from app.services.push_notification_service import send_push_to_staff
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.base_models import Account
from app.utils.hierarchy import (
    STAFF_GEO_LEVEL_FIELDS,
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
    filter_staff_queryset_by_requester_scope,
)


class VehicleBreakdownViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        VehicleBreakdown.objects.select_related(
            "trip_assignment_id",
            "trip_assignment_id__trip_plan_id",
            "trip_assignment_id__staff_template_id",
            "trip_assignment_id__staff_template_id__driver_id",
            "trip_assignment_id__staff_template_id__operator_id",
            "trip_assignment_id__corporation",
            "trip_assignment_id__municipality",
            "trip_assignment_id__town_panchayat",
            "trip_assignment_id__panchayat_union",
            "trip_assignment_id__panchayat",
            "breakdown_vehicle_id",
            "replacement_vehicle_id",
            "replacement_driver_id",
            "replacement_operator_id",
            "alt_staff_template_id",
            "approved_by",
        )
        .prefetch_related("photos")
        .filter(is_deleted=False)
    )
    serializer_class = VehicleBreakdownSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    lookup_field = "unique_id"
    permission_resource = "VehicleBreakdown"

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "vehicle-breakdowns"

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        trip_date = params.get("date") or params.get("trip_date")
        trip_assignment = params.get("trip_assignment_id")
        approval_status = params.get("approval_status")
        breakdown_status = params.get("status")
        breakdown_reason = params.get("breakdown_reason")
        search = params.get("search") or params.get("q")

        if trip_date:
            qs = qs.filter(trip_assignment_id__trip_date=trip_date)
        if trip_assignment:
            qs = qs.filter(trip_assignment_id__unique_id=trip_assignment)
        if approval_status:
            qs = qs.filter(approval_status=approval_status)
        if breakdown_status:
            qs = qs.filter(status=breakdown_status)
        if breakdown_reason:
            qs = qs.filter(breakdown_reason=breakdown_reason)
        if search:
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(breakdown_vehicle_id__vehicle_no__icontains=search)
                | Q(replacement_vehicle_id__vehicle_no__icontains=search)
                | Q(replacement_driver_id__employee_name__icontains=search)
                | Q(replacement_operator_id__employee_name__icontains=search)
            )

        qs = filter_flat_geo_queryset_by_params(
            qs,
            params,
            prefix="trip_assignment_id__",
        )

        # Breakdowns carry no geo columns of their own — scope through the
        # linked assignment's flat geo fields.
        qs = filter_flat_geo_queryset_by_requester_scope(
            qs,
            self.request.user,
            field_map={f: f"trip_assignment_id__{f}" for f in STAFF_GEO_LEVEL_FIELDS},
        )

        return qs

    def _get_account(self):
        from django.contrib.auth import get_user_model

        user = getattr(self.request, "user", None)
        if not user or getattr(user, "is_anonymous", False):
            return None

        # JWT-authenticated requests resolve `request.user` to a
        # Staffcreation row directly (not a User instance) for staff
        # logins — querying Account.objects.filter(user=user) with that
        # raises ValueError, so check the staff case first.
        if hasattr(user, "staff_unique_id"):
            account, _ = Account.objects.get_or_create(staff=user)
            return account

        if isinstance(user, get_user_model()):
            account, _ = Account.objects.get_or_create(user=user)
            return account

        unique_id = getattr(user, "unique_id", None) or getattr(user, "username", None)
        if unique_id:
            return Account.objects.filter(account_id=unique_id).first()

        return None

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            return Response(
                {"detail": "Approved breakdown records are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Approved breakdown records cannot be deleted.")

        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active", "updated_at"])
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

    # ── verify action (mirrors DailyTripLogViewSet.verify) ───────────

    @swagger_auto_schema(request_body=VehicleBreakdownVerifySerializer)
    @action(detail=True, methods=["patch"], url_path="verify")
    def verify(self, request, unique_id=None):
        instance = self.get_object()
        serializer = VehicleBreakdownVerifySerializer(
            data=request.data,
            context={
                "instance": instance,
                "request": request,
                "account": self._get_account(),
            },
        )
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)
        instance = serializer.save()
        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        driver = instance.replacement_driver_id
        if driver is not None:
            send_push_to_staff(
                driver,
                title="Vehicle replaced",
                body=(
                    f"Your vehicle on trip {instance.trip_assignment_id.unique_id} "
                    f"has been replaced with {getattr(instance.replacement_vehicle_id, 'vehicle_no', 'a new vehicle')}."
                ),
                data={
                    "type": "vehicle_breakdown_approved",
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": instance.trip_assignment_id.unique_id,
                },
            )

        return Response(
            VehicleBreakdownSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ── reject action ─────────────────────────────────────────────────

    @swagger_auto_schema(request_body=VehicleBreakdownRejectSerializer)
    @action(detail=True, methods=["patch"], url_path="reject")
    def reject(self, request, unique_id=None):
        instance = self.get_object()
        serializer = VehicleBreakdownRejectSerializer(
            data=request.data,
            context={
                "instance": instance,
                "request": request,
            },
        )
        serializer.is_valid(raise_exception=True)

        previous_data = self._serialize_instance(instance)
        instance = serializer.save()
        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            VehicleBreakdownSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ── available-staff action ────────────────────────────────────────
    # Returns staff NOT already assigned to any Scheduled/In-Progress trip on the given date.
    # role param: "company_driver" / "Company Driver" (case/format-insensitive)

    @action(detail=False, methods=["get"], url_path="available-staff")
    def available_staff(self, request):
        from app.models.superadmin.user_management.staffcreation import Staffcreation

        trip_date = request.query_params.get("date")
        role = request.query_params.get("role")
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not role:
            return Response(
                {"detail": "role query param is required (e.g. 'Company Driver')."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        role_value = role.strip().lower().replace(" ", "_")
        is_driver_role = "driver" in role_value
        is_operator_role = "operator" in role_value

        active_assignments = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ).select_related("staff_template_id", "alt_staff_template_id")

        busy_driver_ids = set()
        busy_operator_ids = set()
        for a in active_assignments:
            tmpl = a.alt_staff_template_id or a.staff_template_id
            if not tmpl:
                continue
            if tmpl.driver_id_id:
                busy_driver_ids.add(tmpl.driver_id_id)
            if tmpl.operator_id_id:
                busy_operator_ids.add(tmpl.operator_id_id)

        # Government staff carry their role on `governmentusertype_id` (e.g.
        # `govt_panchayat_driver`), not `staffusertype_id` (main-backend
        # convention) — match either so this endpoint works on both.
        qs = Staffcreation.objects.filter(
            Q(governmentusertype_id__name__iexact=role_value)
            | Q(staffusertype_id__name__iexact=role_value),
            is_deleted=False,
            active_status=True,
        )

        if is_driver_role:
            qs = qs.exclude(staff_unique_id__in=busy_driver_ids)
        elif is_operator_role:
            qs = qs.exclude(staff_unique_id__in=busy_operator_ids)

        qs = filter_staff_queryset_by_requester_scope(qs, request.user)

        data = [
            {
                "staff_unique_id": s.staff_unique_id,
                "employee_name": s.employee_name,
            }
            for s in qs.order_by("employee_name")
        ]
        return Response(data)

    # ── available-vehicles action ─────────────────────────────────────
    # Returns vehicles NOT assigned to any Scheduled/In-Progress trip on the given date.

    @action(detail=False, methods=["get"], url_path="available-vehicles")
    def available_vehicles(self, request):
        trip_date = request.query_params.get("date")
        if not trip_date:
            return Response(
                {"detail": "date query param is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        busy_vehicle_ids = DailyTripAssignment.objects.filter(
            trip_date=trip_date,
            status__in=[
                DailyTripAssignment.STATUS_SCHEDULED,
                DailyTripAssignment.STATUS_IN_PROGRESS,
            ],
            is_deleted=False,
        ).values_list("vehicle_id", flat=True)

        # When editing an existing breakdown, exclude it from the pending filter
        # so its own replacement vehicle is still shown as available.
        current_breakdown_id = request.query_params.get("exclude_id")
        pending_qs = VehicleBreakdown.objects.filter(
            trip_assignment_id__trip_date=trip_date,
            approval_status=VehicleBreakdown.APPROVAL_PENDING,
            replacement_vehicle_id__isnull=False,
            is_deleted=False,
        )
        if current_breakdown_id:
            pending_qs = pending_qs.exclude(unique_id=current_breakdown_id)
        pending_replacement_ids = pending_qs.values_list("replacement_vehicle_id", flat=True)

        qs = VehicleCreation.objects.filter(
            is_deleted=False,
            is_active=True,
        ).exclude(unique_id__in=busy_vehicle_ids).exclude(unique_id__in=pending_replacement_ids)

        data = [
            {
                "unique_id": v.unique_id,
                "vehicle_no": v.vehicle_no,
                "capacity": str(v.capacity) if v.capacity else None,
            }
            for v in qs.order_by("vehicle_no")
        ]
        return Response(data)

    # ── audit hooks ───────────────────────────────────────────────────

    def perform_create(self, serializer):
        super().perform_create(serializer)
        instance = serializer.instance

        photos = self.request.FILES.getlist("photos")
        for photo in photos:
            VehicleBreakdownPhoto.objects.create(breakdown=instance, photo=photo)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=self._serialize_instance(instance),
        )

        assignment = instance.trip_assignment_id
        trip_plan = getattr(assignment, "trip_plan_id", None)
        supervisor = getattr(trip_plan, "supervisor_id", None)
        if supervisor is not None:
            vehicle_no = getattr(instance.breakdown_vehicle_id, "vehicle_no", "A vehicle")
            send_push_to_staff(
                supervisor,
                title="Vehicle breakdown reported",
                body=f"{vehicle_no} broke down on trip {assignment.unique_id}.",
                data={
                    "type": "vehicle_breakdown_reported",
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": assignment.unique_id,
                    "latitude": str(instance.breakdown_lat or ""),
                    "longitude": str(instance.breakdown_lng or ""),
                },
            )

    def perform_update(self, serializer):
        previous_data = self._serialize_instance(serializer.instance)
        super().perform_update(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
