from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.management.commands.seeders.ward_utils import geo_defaults_for_local_body, local_bodies_for_district
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails

SLOTS_PER_WARD = 2  # one template for the ward's bin route, one for its household route


class StaffTemplateSeeder(BaseSeeder):
    """One StaffTemplate per (local body, ward, collection-type) slot: every
    local body (Corporation, Municipality, Town Panchayat, Panchayat Union,
    each Panchayat) owns a pool of driver/operator crews sized to exactly
    its own ward_count x 2 — never shared with another local body's trip
    plans, and no pairing is ever reused district-wide. Sized against
    StaffOfficeSeeder's 9 drivers x 9 operators per district (81 possible
    pairings), which comfortably covers even the largest district's total
    ward-slot count. Fully geo-scoped to the owning local body (previously
    left null on every field)."""

    name = "StaffTemplateSeeder"

    def run(self):
        count = 0
        for district_name in DISTRICTS:
            drivers = list(
                StaffcreationOfficeDetails.objects.filter(
                    district__name=district_name, designation="Vehicle Driver", is_deleted=False,
                ).order_by("staff_unique_id")
            )
            operators = list(
                StaffcreationOfficeDetails.objects.filter(
                    district__name=district_name, designation="Waste Collector", is_deleted=False,
                ).order_by("staff_unique_id")
            )
            approver = StaffcreationOfficeDetails.objects.filter(
                district__name=district_name, designation="Field Supervisor", is_deleted=False,
            ).first()
            local_bodies = local_bodies_for_district(district_name)
            if not drivers or not operators or not local_bodies:
                self.log(f"Missing drivers/operators/local bodies for '{district_name}' — skipping.")
                continue

            combos = [(d, o) for d in drivers for o in operators]
            total_slots = sum(lb["ward_count"] * SLOTS_PER_WARD for lb in local_bodies)
            if len(combos) < total_slots:
                self.log(
                    f"'{district_name}': only {len(combos)} driver/operator pairings for "
                    f"{total_slots} local-body slots — some will be skipped."
                )

            combo_idx = 0
            for lb in local_bodies:
                geo_defaults = geo_defaults_for_local_body(lb["parent_type"], lb["parent"])
                slots = lb["ward_count"] * SLOTS_PER_WARD
                for slot in range(slots):
                    if combo_idx >= len(combos):
                        break
                    driver, operator = combos[combo_idx]
                    combo_idx += 1
                    extra_operator = operators[combo_idx % len(operators)]

                    _, created = StaffTemplate.objects.update_or_create(
                        driver_id=driver,
                        operator_id=operator,
                        defaults={
                            **geo_defaults,
                            "extra_operator_id": [extra_operator.staff_unique_id],
                            "approved_by": approver,
                            "approval_status": StaffTemplate.ApprovalStatus.APPROVED,
                            "status": StaffTemplate.Status.ACTIVE,
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )
                    if created:
                        count += 1

        self.log(f"---Staff templates seeded ({count} created)---")
