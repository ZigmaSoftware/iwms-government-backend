from django.db import models
from app.utils.base_models import BaseMaster
from .country import Country
from .continent import Continent
from app.utils.comfun import generate_unique_id


def generate_state_id():
    return f"STATE-{generate_unique_id()}"


class State(BaseMaster):

    CASCADE_SOFT_DELETE = (
        "districts",
        "area_type",
        "corporations",
        "municipalities",
        "town_panchayats",
        "panchayat_unions",
        "panchayat",
        "wards",
        # consumer tables referencing this state directly
        "leader_logins",
        "bins",
        "vehicles",
        "staff_templates",
        "collection_points",
        "trip_plans",
        "trip_plan_collection_points",
        "daily_trip_logs",
        "daily_trip_collection_points",
        "daily_trip_assignments",
        "daily_trip_household_collections",
        "vehicle_breakdowns",
        "secondary_bin_collection_events",
        "waste_collections",
        "complaint_routing_rules",
        "address_change_requests",
        "complaint_tickets",
        "scoped_staff",
        "staff_members",
        "userscreen_column_permissions",
        "dashboard_widget_permissions",
        "userscreenpermissions",
        "customer_creations",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("state_list", "state_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_state_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="states",
        to_field="unique_id",
        db_column="country_id",
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="states",
        to_field="unique_id",
        db_column="continent_id",
    )

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("country_id", "name")

    def __str__(self):
        return f"{self.name} ({self.country_id.name})"
