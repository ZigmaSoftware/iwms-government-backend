"""An audited plan-level decision that collection will not run on a date.

Declared by the plan's supervisor from the supervisor app ("No collection
today", DailyTripAssignmentViewSet.no_collection); app/services/
daily_service_notice.py cancels the day's scheduled trips, notifies the crew
and every customer the plan serves, and the trip generators skip the plan
while the notice is ACTIVE. Revoking it restores the cancelled trips.

Plain id references only (no DB relations), and the plan's flat geography is
copied on save so the rows can be geo-scoped like their siblings.
"""

from django.db import models

from app.utils import ref_cache
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


def generate_daily_service_notice_id():
    return f"DSN-{generate_unique_id()}"


class DailyServiceNotice(BaseMaster):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_REVOKED = "REVOKED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_REVOKED, "Revoked"),
    ]

    REASON_WEATHER = "WEATHER"
    REASON_FLOOD = "FLOOD"
    REASON_HOLIDAY = "HOLIDAY"
    REASON_STAFF_UNAVAILABLE = "STAFF_UNAVAILABLE"
    REASON_VEHICLE_TECHNICAL = "VEHICLE_TECHNICAL"
    REASON_SAFETY = "SAFETY"
    REASON_OTHER = "OTHER"
    REASON_CHOICES = [
        (REASON_WEATHER, "Severe weather"),
        (REASON_FLOOD, "Flooding"),
        (REASON_HOLIDAY, "Public holiday"),
        (REASON_STAFF_UNAVAILABLE, "Staff unavailable"),
        (REASON_VEHICLE_TECHNICAL, "Vehicle or technical issue"),
        (REASON_SAFETY, "Safety issue"),
        (REASON_OTHER, "Other"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_service_notice_id,
        editable=False,
    )
    # TripPlan.unique_id (plain string, no DB relation).
    trip_plan_id = models.CharField(max_length=30, db_index=True)
    # Staffcreation.staff_unique_id of the plan's supervisor at declaration.
    supervisor_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    service_date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    reason_code = models.CharField(max_length=30, choices=REASON_CHOICES)
    reason_text = models.CharField(max_length=500, blank=True, default="")
    # Staffcreation.staff_unique_id / CustomerCreation.unique_id lists.
    recipient_staff_ids = models.JSONField(default=list, blank=True)
    recipient_customer_ids = models.JSONField(default=list, blank=True)
    staff_notified_count = models.PositiveIntegerField(default=0)
    customer_notified_count = models.PositiveIntegerField(default=0)
    notification_failed_count = models.PositiveIntegerField(default=0)
    notified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # Account id of whoever revoked it (same shape as BaseMaster.updated_by).
    revoked_by_id = models.CharField(max_length=50, null=True, blank=True)
    revoked_reason = models.CharField(max_length=500, blank=True, default="")

    # ── Flat geo scope block (copied from the TripPlan on save) ─────────
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward_ids = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "service_date"],
                name="uniq_daily_service_notice_plan_date",
            ),
        ]
        indexes = [
            models.Index(fields=["supervisor_id", "service_date", "status"]),
        ]

    def __str__(self):
        return f"{self.trip_plan_id} - {self.service_date} - {self.status}"

    def save(self, *args, **kwargs):
        if self.trip_plan_id and not self.district_id:
            plan = self.trip_plan
            if plan is not None:
                copy_flat_geo(self, plan, only_empty=True)
                if not self.ward_ids:
                    self.ward_ids = list(plan.ward_ids or [])
        super().save(*args, **kwargs)

    @property
    def trip_plan(self):
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan

        return ref_cache.get(TripPlan, self.trip_plan_id, "unique_id")

    @property
    def supervisor(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        return ref_cache.get(Staffcreation, self.supervisor_id)
