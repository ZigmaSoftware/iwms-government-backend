from django.db import models

from app.utils.base_models import BaseMaster
from app.models.superadmin.common_masters.state import State
from app.models.masters.state_leader_login import generate_state_leader_id


class StateLeaderLogin(BaseMaster):
    """
    Login credentials for a state local-body leader.
    Each record is scoped to exactly one State.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_state_leader_id,
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="leader_logins",
        db_column="state_id",
        to_field="unique_id",
    )

    # Dynamic geography: the hierarchy node this leader is scoped to. Replaces
    # the static state_id (kept temporarily for zero-downtime migration).
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.SET_NULL,
        related_name="state_leader_logins",
        to_field="unique_id",
        db_column="location_node_id",
        null=True,
        blank=True,
    )

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Login username for the state leader.",
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
        help_text="Full name of the state leader.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "State Leader Login"
        verbose_name_plural = "State Leader Logins"

    def __str__(self):
        return f"{self.username} ({self.state_id.name if self.state_id else '—'})"

    # Required by DRF permission system
    @property
    def is_authenticated(self):
        return True
