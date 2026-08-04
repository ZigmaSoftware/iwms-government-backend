"""Driver request to close a trip that still has unfinished stops.

A driver who runs out of shift, fills the vehicle, or hits a blocked road can
neither finish the remaining stops nor legitimately end the trip — before this,
the assignment simply sat `In Progress` forever, because nothing auto-closes a
trip and a `Skipped` stop permanently blocks `mark_completed_if_all_cps_collected`.

The Re-Trip flow gives that state an exit:

    driver ends with N stops left
      -> TripRetripRequest(Pending) + mandatory reason; trip STAYS In Progress
      -> supervisor reviews, picks what carries over, approves
      -> old assignment ends, a NEW assignment on the same trip plan is created
         carrying only the selected stops

The trip deliberately keeps its `In Progress` status while a request is pending
so `DailyTripAssignment.STATUS_CHOICES` and the existing
`DailyTripAssignmentStatusSerializer.VALID_TRANSITIONS` state machine stay
untouched — the app learns about the pending request from the serializer block
instead of from a new status value.
"""

from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staffcreation import Staffcreation


def generate_retrip_request_id():
    return f"RETRIP-{generate_unique_id()}"


class TripRetripRequest(BaseMaster):
    STATUS_PENDING = "Pending"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_retrip_request_id,
        editable=False,
    )

    assignment = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        related_name="retrip_requests",
    )
    requested_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrip_requests_raised",
    )

    # Mandatory — the whole point of the gate is that the driver has to say why
    # the trip is being cut short.
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    # Snapshot taken when the request is raised. Stops can change between
    # request and approval (a colleague may collect one), so the supervisor's
    # screen shows live counts — these are the audit record of what the driver
    # was actually looking at.
    pending_bin_count = models.IntegerField(default=0)
    pending_household_count = models.IntegerField(default=0)
    pending_snapshot = models.JSONField(default=dict, blank=True)

    reviewed_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrip_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(null=True, blank=True)

    # The continuation trip created on approval.
    new_assignment = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrip_source_requests",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Re-Trip Request"
        verbose_name_plural = "Re-Trip Requests"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.unique_id} ({self.assignment_id} · {self.status})"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING

    def mark_reviewed(self, *, status, by=None, remarks=None, new_assignment=None):
        self.status = status
        self.reviewed_by = by
        self.reviewed_at = timezone.now()
        self.review_remarks = remarks
        if new_assignment is not None:
            self.new_assignment = new_assignment
        self.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_remarks",
            "new_assignment", "updated_at",
        ])
