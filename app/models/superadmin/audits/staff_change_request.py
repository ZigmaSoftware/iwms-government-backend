from django.db import models

from app.utils.comfun import generate_unique_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation


def generate_change_request_id():
    return f"CHGREQ-{generate_unique_id()}"


class StaffChangeRequest(models.Model):
    """Staff self-service request to change one of their own profile fields
    (e.g. contact_mobile, present_address), subject to their supervisor's
    approval. `approver_id` is captured at submission time from the
    requester's `staff_head_id` so routing stays stable even if the org
    chart changes later, and is a plain unique_id string (not a live FK) to
    match how `staff_head_id` itself is modeled."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    # Fields on StaffPersonalDetails this workflow is allowed to change.
    # Kept here (not just enforced in the serializer) so the allow-list is
    # visible next to the data it gates.
    ALLOWED_FIELDS = (
        "contact_mobile",
        "contact_email",
        "present_address",
        "permanent_address",
    )

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_change_request_id,
        editable=False,
    )

    requested_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.CASCADE,
        to_field="staff_unique_id",
        related_name="change_requests",
    )
    approver_id = models.CharField(max_length=30, null=True, blank=True)

    field_name = models.CharField(max_length=50)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    decided_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="staff_unique_id",
        related_name="change_requests_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_change_requests"
        ordering = ["-created_at"]
