from django.db import models
from app.utils.base_models import BaseMaster
from ..superadmin.common_masters.country import Country
from ..superadmin.common_masters.state import State
from ..superadmin.common_masters.continent import Continent
from app.utils.comfun import generate_unique_id



def generate_district_id():
    return f"DIST-{generate_unique_id()}"

class District(BaseMaster):

    CASCADE_SOFT_DELETE = (
        "area_type",
        "corporations",
        "municipalities",
        "town_panchayats",
        "panchayat_unions",
        "panchayat",
        "wards",
        # consumer tables referencing this district directly
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
        "users_district",
        "customer_creations",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("district_list", "district_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="country_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="state_id",
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="continent_id",
    )

    name = models.CharField(max_length=100)
    district_code = models.CharField(max_length=20, blank=True, null=True)
    coordinates = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "name")   # FIXED

    def __str__(self):
        return f"{self.name} ({self.state_id.name})"
