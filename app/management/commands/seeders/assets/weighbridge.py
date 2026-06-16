# from datetime import date
# from decimal import Decimal

# from app.management.commands.seeders.base import BaseSeeder

# from app.models.assets.weighbridge import WeighbridgeCheck
# from app.models.transport_masters.trip import Trip
# from app.models.superadmin_masters.company import Company
# from app.models.superadmin_masters.project import Project

# from django.db import models

# class WeighbridgeCheckSeeder(BaseSeeder):
#     name = "weighbridge_check"

#     def run(self):

#         # --------------------------------------------------
#         # COMPANY & PROJECT
#         # --------------------------------------------------
#         company = Company.objects.get(name="IWMS")
#         project = Project.objects.get(name=f"{company.name} Main Project")

#         # --------------------------------------------------
#         # GET TRIP (must exist)
#         # --------------------------------------------------

#         if not trip:
#             self.log("No Trip found. Skipping WeighbridgeCheck.")
#             return

#         # Ensure trip has point collections
#         if not trip.point_collections.exists():
#             self.log("Trip has no PointCollections. Skipping WeighbridgeCheck.")
#             return

#         # --------------------------------------------------
#         # CALCULATE TOTAL COLLECTED
#         # --------------------------------------------------
#         total_collected = trip.point_collections.aggregate(
#             total=models.Sum("point_collection_weight")
#         )["total"] or Decimal("0.00")

#         # Slight variation to test status logic
#         weighbridge_weight = total_collected + Decimal("1.00")

#         # --------------------------------------------------
#         # CREATE / UPDATE WEIGHBRIDGE CHECK
#         # --------------------------------------------------
#         wbc, created = WeighbridgeCheck.objects.update_or_create(
#             trip_id=trip,
#             defaults={
#                 "company_id": company,
#                 "project_id": project,
#                 "weighbridge_weight": weighbridge_weight,
#                 "checked_date": date.today(),
#                 "collected_date": date.today(),
#                 "is_active": True,
#                 "is_deleted": False,
#             },
#         )

#         action = "Created" if created else "Updated"

#         self.log(
#             f"---WeighbridgeCheck seeded: {wbc.unique_id} "
#             f"(Status: {wbc.status}) ({action})---"
#         )
