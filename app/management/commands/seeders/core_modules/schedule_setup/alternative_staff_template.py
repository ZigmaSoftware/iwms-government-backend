from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.ward_utils import FLAT_GEO_FIELDS
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails

REASONS = ["Sick leave", "Annual leave", "Emergency replacement", "Training duty", "Vehicle change"]
REMARKS = [
    "Regular driver on approved leave; substitute crew assigned for the duration.",
    "Operator requested a schedule swap; approved for the listed date range.",
    "Emergency stand-in arranged after last-minute unavailability.",
    "Crew sent for mandatory safety/refresher training.",
    "Vehicle swap required a different driver familiar with the replacement vehicle.",
]


class AlternativeStaffTemplateSeeder(BaseSeeder):
    """One alternate driver/operator pairing per StaffTemplate, drawn from
    other staff in that same district (works across all 3 operational
    districts, not just one fixed set of names)."""

    name = "AlternativeStaffTemplateSeeder"

    def run(self):
        templates = StaffTemplate.objects.filter(
            is_deleted=False, status=StaffTemplate.Status.ACTIVE
        ).select_related("driver_id__district", "operator_id").order_by("created_at")

        if not templates.exists():
            self.log("No StaffTemplates found — run StaffTemplateSeeder first.")
            return

        base_date = timezone.localdate()
        count = 0
        updated = 0
        for idx, template in enumerate(templates):
            district = template.driver_id.district if template.driver_id_id else None
            if not district:
                self.log(f"Template '{template.display_code}' has no district — skipping.")
                continue

            candidates = list(
                StaffcreationOfficeDetails.objects.filter(district=district, is_deleted=False)
                .exclude(staff_unique_id__in=[template.driver_id_id, template.operator_id_id])
                .order_by("staff_unique_id")
            )
            if len(candidates) < 2:
                self.log(f"Not enough alternate staff in '{district.name}' — skipping.")
                continue

            alt_driver, alt_operator = candidates[0], candidates[1]
            extra_operator = candidates[2] if len(candidates) > 2 else alt_operator
            reason = REASONS[idx % len(REASONS)]
            remarks = REMARKS[idx % len(REMARKS)]
            from_date = base_date + timedelta(days=idx + 1)
            to_date = from_date + timedelta(days=6)
            geo_defaults = {field: getattr(template, field, None) for field in FLAT_GEO_FIELDS}
            approver = template.approved_by

            existing = AlternativeStaffTemplate.objects.filter(staff_template=template).first()
            if existing:
                existing.driver_id = alt_driver
                existing.operator_id = alt_operator
                existing.extra_operator_id = [extra_operator.staff_unique_id]
                existing.change_reason = reason
                existing.change_remarks = remarks
                existing.approved_by = approver
                existing.from_date = existing.from_date or from_date
                existing.to_date = existing.to_date or to_date
                existing.approval_status = "APPROVED"
                for field, value in geo_defaults.items():
                    setattr(existing, field, value)
                existing.save()
                updated += 1
                self.log(f"Updated alt template for '{template.display_code}'.")
                continue

            AlternativeStaffTemplate.objects.create(
                staff_template=template,
                driver_id=alt_driver,
                operator_id=alt_operator,
                extra_operator_id=[extra_operator.staff_unique_id],
                from_date=from_date,
                to_date=to_date,
                change_reason=reason,
                change_remarks=remarks,
                approved_by=approver,
                approval_status="APPROVED",
                **geo_defaults,
            )
            count += 1

        self.log(f"---Alternative staff templates seeded ({count} created, {updated} updated)---")
