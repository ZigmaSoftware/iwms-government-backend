from app.management.commands.seeders.base import BaseSeeder

from app.models.assets.bins import Bins, BinType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


class BinSeeder(BaseSeeder):
    name = "bin"

    def _get_waste_type(self, name):
        return WasteType.objects.filter(
            waste_type_name__iexact=name, is_deleted=False
        ).first()

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        wet_waste = self._get_waste_type("Wet Waste")
        dry_waste = self._get_waste_type("Dry Waste")
        any_waste = wet_waste or WasteType.objects.filter(is_deleted=False).first()

        if not any_waste:
            self.log("No WasteType found — aborting BinSeeder.")
            return

        created_count = 0

        # --- Ward CPs: 1 bin (any waste type) per ward CP ---
        ward_cps = Collection_point.objects.filter(
            company_id=company,
            project_id=project,
            ward_id__isnull=False,
            is_deleted=False,
        ).order_by("cp_name")

        for cp in ward_cps:
            cp_key = cp.unique_id[-6:]   # last 6 chars of PK for a compact unique suffix
            bin_name = f"{cp.cp_name} Bin"
            qr = f"QR-{cp_key}-ANY"
            waste_type = wet_waste or any_waste
            _, created = Bins.objects.get_or_create(
                bin_qr=qr,
                company_id=company,
                project_id=project,
                defaults={
                    "collection_point_id": cp,
                    "wastetype_id": waste_type,
                    "bin_name": bin_name,
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "default.png",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1

        # --- Panchayat CPs: wet + dry bin per panchayat CP ---
        if not wet_waste or not dry_waste:
            self.log("Wet/Dry WasteType not found — skipping panchayat bins.")
            self.log(f"---Bins seeded | created={created_count} (ward bins only)---")
            return

        panchayat_cps = Collection_point.objects.filter(
            company_id=company,
            project_id=project,
            ward_id__isnull=True,
            panchayat_id__isnull=False,
            is_deleted=False,
        ).order_by("panchayat_id", "cp_name")

        for cp in panchayat_cps:
            cp_key = cp.unique_id[-6:]
            for label, waste_type in (("WET", wet_waste), ("DRY", dry_waste)):
                qr = f"QR-{cp_key}-{label}"
                bin_name = f"{cp.cp_name} {label.capitalize()} Bin"
                _, created = Bins.objects.get_or_create(
                    bin_qr=qr,
                    company_id=company,
                    project_id=project,
                    defaults={
                        "collection_point_id": cp,
                        "wastetype_id": waste_type,
                        "bin_name": bin_name,
                        "bin_capacity": 240,
                        "bin_type": BinType.MEDIUM,
                        "bin_image": "default.png",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    created_count += 1

        self.log(
            f"---Bins seeded | created={created_count} "
            f"| ward CPs={ward_cps.count()} | panchayat CPs={panchayat_cps.count()}---"
        )
