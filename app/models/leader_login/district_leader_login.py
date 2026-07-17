from django.db import models

from app.utils.base_models import BaseMaster
from app.models.masters.district import District
from app.models.masters.district_leader_login import generate_district_leader_id


class DistrictLeaderLogin(BaseMaster):
    """
    Login credentials for a district local-body leader.
    Each record is scoped to exactly one District.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_district_leader_id,
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="leader_logins",
        db_column="district_id",
        to_field="unique_id",
    )

    # Dynamic geography: the hierarchy node this leader is scoped to. Replaces
    # the static district_id (kept temporarily for zero-downtime migration).
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.SET_NULL,
        related_name="district_leader_logins",
        to_field="unique_id",
        db_column="location_node_id",
        null=True,
        blank=True,
    )



    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Login username for the district leader.",
    )

    password = models.CharField(
        max_length=128,
        help_text="Hashed password (Django PBKDF2).",
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    leader_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Full name of the district leader.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "District Leader Login"
        verbose_name_plural = "District Leader Logins"

    def __str__(self):
        return f"{self.username} ({self.district_id.name if self.district_id else '—'})"

    # Required by DRF permission system
    @property
    def is_authenticated(self):
        return True
