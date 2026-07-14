from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .userType import UserType


def generate_govt_usertype_id():
    return f"GOVTUSRTYPE-{generate_unique_id()}"


class GovernmentStaffUserType(BaseMaster):

    GOVT_LEVEL_CHOICES = [
        ("state", "State"),
        ("district", "District"),
        ("municipality", "Municipality"),
        ("corporation", "Corporation"),
        ("town_panchayat", "Town Panchayat"),
        ("panchayat_union", "Panchayat Union"),
        ("panchayat", "Panchayat"),
    ]

    GOVT_ROLE_CHOICES = [
        ("govt_state_admin",            "State Admin"),
        ("govt_state_officer",          "State Officer"),
        ("govt_state_inspector",        "State Inspector"),
        ("govt_state_driver",           "State Driver"),
        ("govt_state_operator",         "State Operator"),
        ("govt_district_admin",         "District Admin"),
        ("govt_district_officer",       "District Officer"),
        ("govt_district_inspector",     "District Inspector"),
        ("govt_district_driver",        "District Driver"),
        ("govt_district_operator",      "District Operator"),
        ("govt_municipality_admin",     "Municipality Admin"),
        ("govt_municipality_officer",   "Municipality Officer"),
        ("govt_municipality_inspector", "Municipality Inspector"),
        ("govt_municipality_driver",    "Municipality Driver"),
        ("govt_municipality_operator",  "Municipality Operator"),
        ("govt_corporation_admin",      "Corporation Admin"),
        ("govt_corporation_supervisor", "Corporation Supervisor"),
        ("govt_corporation_officer",    "Corporation Officer"),
        ("govt_corporation_inspector",  "Corporation Inspector"),
        ("govt_corporation_driver",     "Corporation Driver"),
        ("govt_corporation_operator",   "Corporation Operator"),
        ("govt_town_panchayat_admin",      "Town Panchayat Admin"),
        ("govt_town_panchayat_officer",    "Town Panchayat Officer"),
        ("govt_town_panchayat_inspector",  "Town Panchayat Inspector"),
        ("govt_town_panchayat_driver",     "Town Panchayat Driver"),
        ("govt_town_panchayat_operator",   "Town Panchayat Operator"),
        ("govt_panchayat_union_admin",     "Panchayat Union Admin"),
        ("govt_panchayat_union_officer",   "Panchayat Union Officer"),
        ("govt_panchayat_union_inspector", "Panchayat Union Inspector"),
        ("govt_panchayat_union_driver",    "Panchayat Union Driver"),
        ("govt_panchayat_union_operator",  "Panchayat Union Operator"),
        ("govt_panchayat_admin",      "Panchayat Admin"),
        ("govt_panchayat_officer",    "Panchayat Officer"),
        ("govt_panchayat_inspector",  "Panchayat Inspector"),
        ("govt_panchayat_driver",     "Panchayat Driver"),
        ("govt_panchayat_operator",   "Panchayat Operator"),
        # Field supervisors — responsible for driver/operator trips.
        ("govt_state_supervisor",           "State Supervisor"),
        ("govt_district_supervisor",        "District Supervisor"),
        ("govt_municipality_supervisor",    "Municipality Supervisor"),
        ("govt_corporation_supervisor",     "Corporation Supervisor"),
        ("govt_town_panchayat_supervisor",  "Town Panchayat Supervisor"),
        ("govt_panchayat_union_supervisor", "Panchayat Union Supervisor"),
        ("govt_panchayat_supervisor",       "Panchayat Supervisor"),
    ]

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        unique=True,
        default=generate_govt_usertype_id,
        editable=False,
    )

    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="governmentstaffusertypes",
        to_field="unique_id",
    )

    name = models.CharField(
        max_length=60,
        choices=GOVT_ROLE_CHOICES,
    )

    level = models.CharField(
        max_length=20,
        choices=GOVT_LEVEL_CHOICES,
    )

    class Meta:
        ordering = ["level", "name"]
        verbose_name = "Government Staff User Type"
        verbose_name_plural = "Government Staff User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_govt_role_per_usertype_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.get_level_display()} → {self.get_name_display()}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
