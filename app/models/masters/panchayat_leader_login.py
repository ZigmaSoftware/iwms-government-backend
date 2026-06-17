from django.db import models
from django.contrib.auth.hashers import make_password

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.panchayat import Panchayat


def generate_panchayat_leader_id():
    return f"PLDR-{generate_unique_id()}"


class PanchayatLeaderLogin(BaseMaster):
    """
    Login credentials for a panchayat local-body leader.
    Each record is scoped to exactly one Panchayat.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_panchayat_leader_id,
    )

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="leader_logins",
        db_column="panchayat_id",
        to_field="unique_id",
    )



    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Login username for the panchayat leader.",
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
        help_text="Full name of the panchayat leader.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Panchayat Leader Login"
        verbose_name_plural = "Panchayat Leader Logins"

    def __str__(self):
        return f"{self.username} ({self.panchayat_id.panchayat_name if self.panchayat_id else '—'})"

    # Required by DRF permission system
    @property
    def is_authenticated(self):
        return True
