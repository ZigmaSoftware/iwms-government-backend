from django.db import models

from app.utils.comfun import generate_unique_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils import ref_cache


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

    # Staffcreation.staff_unique_id values (plain strings, no DB relation).
    requested_by_id = models.CharField(
        max_length=30, db_column="requested_by_id", db_index=True
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
    decided_by_id = models.CharField(
        max_length=30, db_column="decided_by_id", null=True, blank=True, db_index=True
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_change_requests"
        ordering = ["-created_at"]

    @property
    def requested_by(self):
        return ref_cache.get(Staffcreation, self.requested_by_id)

    @property
    def decided_by(self):
        return ref_cache.get(Staffcreation, self.decided_by_id)
