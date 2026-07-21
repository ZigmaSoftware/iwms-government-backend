from django.db.models import Q
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.serializers.schedule_masters.daily_trip_log_serializer import (
    DailyTripLogSerializer,
    DailyTripLogVerifySerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.base_models import Account
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage


class DailyTripLogViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = (
        DailyTripLog.objects.select_related(
            "trip_assignment_id",
            "trip_assignment_id__trip_plan_id",
            "trip_assignment_id__staff_template_id",
            "trip_assignment_id__staff_template_id__driver_id",
            "trip_assignment_id__staff_template_id__operator_id",
            "trip_assignment_id__alt_staff_template_id",
            "trip_assignment_id__alt_staff_template_id__driver_id",
            "trip_assignment_id__alt_staff_template_id__operator_id",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
            "collection_point_id",
            "driver_id",
            "operator_id",
            "vehicle_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
            "alt_staff_template_id",
            "alt_staff_template_id__driver_id",
            "alt_staff_template_id__operator_id",
            "verified_by",
            "verified_by__staff",
            "verified_by__user",
        )
        .prefetch_related(
            "bin_ids",
            "extra_operator_ids",
            "waste_types",
            "trip_assignment_id__trip_collection_points",
            "trip_assignment_id__trip_collection_points__collection_point_id",
        )
        .filter(is_deleted=False)
    )
    serializer_class = DailyTripLogSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripLog"
    pagination_class = LimitOffsetWithPage

    AUDIT_MODULE = "trip-logs"
    AUDIT_ENDPOINT = "daily-trip-logs"

    def _get_account(self):
        user = getattr(self.request, "user", None)
        if not user or getattr(user, "is_anonymous", False):
            return None

        account = Account.objects.filter(user=user).first()
        if account:
            return account

        staff = getattr(user, "staff", None)
        if staff:
            account = Account.objects.filter(staff=staff).first()
            if account:
                return account

        unique_id = getattr(user, "unique_id", None) or getattr(user, "username", None)
        if unique_id:
            return Account.objects.filter(account_id=unique_id).first()

        return None

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        trip_date = params.get("date") or params.get("trip_date")
        status_value = params.get("status") or params.get("log_status")
        assignment = params.get("trip_assignment_id")
        collection_point = params.get("collection_point_id")
        waste_type = params.get("waste_type_id")
        driver = params.get("driver_id")
        operator = params.get("operator_id")
        search = params.get("search") or params.get("q")

        if trip_date:
            qs = qs.filter(trip_date=trip_date)
        if status_value:
            qs = qs.filter(log_status=status_value)
        if assignment:
            qs = qs.filter(trip_assignment_id=assignment)
        if collection_point:
            qs = qs.filter(collection_point_id=collection_point)
        if waste_type:
            qs = qs.filter(waste_types__unique_id=waste_type)
        if driver:
            qs = qs.filter(driver_id=driver)
        if operator:
            qs = qs.filter(operator_id=operator)
        if search:
            qs = qs.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(collection_point_id__cp_name__icontains=search)
                | Q(waste_types__waste_type_name__icontains=search)
                | Q(driver_id__employee_name__icontains=search)
                | Q(operator_id__employee_name__icontains=search)
                | Q(vehicle_id__vehicle_no__icontains=search)
            )

        if waste_type or search:
            qs = qs.distinct()

        ordering = params.get("ordering")
        allowed_ordering = {
            "unique_id",
            "-unique_id",
            "trip_date",
            "-trip_date",
            "collected_weight_kg",
            "-collected_weight_kg",
            "log_status",
            "-log_status",
            "created_at",
            "-created_at",
        }
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)

        qs = filter_flat_geo_queryset_by_params(qs, params)
        qs = filter_flat_geo_queryset_by_requester_scope(qs, self.request.user)

        return qs

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            return Response(
                {"detail": "Verified trip logs are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Verified trip logs are read-only.")

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

    @swagger_auto_schema(request_body=DailyTripLogVerifySerializer)
    @action(detail=True, methods=["patch"], url_path="verify")
    def verify(self, request, unique_id=None):
        instance = self.get_object()
        serializer = DailyTripLogVerifySerializer(
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

        return Response(
            DailyTripLogSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(request_body=DailyTripLogVerifySerializer)
    @action(detail=True, methods=["patch"], url_path="change-status")
    def change_status(self, request, unique_id=None):
        instance = self.get_object()
        new_status = request.data.get("log_status", "").strip()
        remarks = request.data.get("remarks", "")

        valid = {
            DailyTripLog.LOG_STATUS_DRAFT,
            DailyTripLog.LOG_STATUS_SUBMITTED,
            DailyTripLog.LOG_STATUS_VERIFIED,
        }
        if new_status not in valid:
            return Response(
                {"detail": f"Invalid status. Valid options: {', '.join(sorted(valid))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status == instance.log_status:
            return Response(
                {"detail": f"Log is already in '{new_status}' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_data = self._serialize_instance(instance)
        account = self._get_account()
        now = timezone.now()

        update_fields = {
            "log_status": new_status,
            "updated_at": now,
        }
        if remarks:
            update_fields["remarks"] = remarks
        if new_status == DailyTripLog.LOG_STATUS_VERIFIED:
            update_fields["verified_by_id"] = account.pk if account else None
            update_fields["verified_at"] = now
        elif new_status == DailyTripLog.LOG_STATUS_DRAFT:
            update_fields["verified_by_id"] = None
            update_fields["verified_at"] = None

        DailyTripLog.objects.filter(pk=instance.pk).update(**update_fields)
        instance.refresh_from_db()

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        return Response(
            DailyTripLogSerializer(instance, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def perform_create(self, serializer):
        previous_data = None
        super().perform_create(serializer)
        instance = serializer.instance
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
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
