from .alternative_staff_template import AlternativeStaffTemplateSeeder
from .bin_collection_event import BinCollectionEventSeeder
from .collection_point import CollectionPointSeeder
from app.management.commands.seeders.assets.bins import BinSeeder
from .daily_trip_assignment import DailyTripAssignmentSeeder
from .daily_trip_collection_point import DailyTripCollectionPointSeeder
from .daily_trip_household_collection import DailyTripHouseholdCollectionSeeder
from .daily_trip_log import DailyTripLogSeeder
from .staff_template import StaffTemplateSeeder
from .trip_plan import TripPlanSeeder
from .trip_plan_collection_point import TripPlanCollectionPointSeeder

SCHEDULE_MASTER_SEEDERS = [
    CollectionPointSeeder,          # 1. Physical GPS stops
    BinSeeder,                      # 2. Bins at each CP (must follow CollectionPoint)
    StaffTemplateSeeder,            # 3. Driver+Operator pairings
    AlternativeStaffTemplateSeeder, # 4. Substitute pairings
    TripPlanSeeder,                 # 5. Route blueprints
    TripPlanCollectionPointSeeder,  # 6. Stop list per plan
    DailyTripAssignmentSeeder,      # 7. Daily schedule instances
    DailyTripCollectionPointSeeder, # 8. Per-day stop instances
    DailyTripHouseholdCollectionSeeder,
    DailyTripLogSeeder,             # 9. End-of-trip summaries
    BinCollectionEventSeeder,       # Immutable scan audit log
]
