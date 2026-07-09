from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.category_master import ComplaintCategory
from app.models.complaint_ticket.comment import ComplaintComment
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.source_master import ComplaintSource
from app.models.complaint_ticket.status_history import ComplaintStatusHistory
from app.models.complaint_ticket.status_master import ComplaintStatus
from app.models.complaint_ticket.subcategory_master import ComplaintSubcategory
from app.models.complaint_ticket.team_master import ComplaintTeam
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.customers.customercreation import CustomerCreation


class ComplaintTicketSeeder(BaseSeeder):
    name = "complaint_ticket"

    # (key, customer_index, category_code, subcategory_code, priority_code,
    #  status_code, source_code, team_code, title, description)
    TICKETS = [
        (
            "seed-missed-pickup-001",
            0,
            "MISSED_PICKUP",
            "NOT_COLLECTED",
            "P2",
            "SUBMITTED",
            "WHATSAPP",
            "SANITATION",
            "Waste was not collected today",
            "Household waste was kept outside before the scheduled time but was not collected.",
        ),
        (
            "seed-bulk-waste-001",
            2,
            "BULK_WASTE",
            "FURNITURE",
            "P3",
            "ASSIGNED",
            "CALL_CENTER",
            "SANITATION",
            "Bulk furniture pickup request",
            "Customer requested pickup for old furniture items from the apartment block.",
        ),
        (
            "seed-address-change-001",
            1,
            "ADDRESS_CHANGE",
            "SERVICE_ADDRESS",
            "P3",
            "RESOLVED",
            "WEB",
            "ADDRESS_DESK",
            "Service address correction",
            "Customer requested service address correction after moving to a nearby street.",
        ),
        (
            "seed-worker-conduct-001",
            3,
            "WORKER_CONDUCT",
            "BEHAVIOUR",
            "P2",
            "CLOSED",
            "MOBILE_APP",
            "SANITATION_L2",
            "Worker conduct complaint",
            "Complaint about rude behaviour during morning collection.",
        ),
    ]

    def run(self):
        customers = list(CustomerCreation.objects.filter(is_deleted=False, is_active=True).order_by("customer_name"))
        if not customers:
            self.log("No active customers found - run customer-masters seeders first.")
            return

        created_or_updated = 0
        now = timezone.now()

        for (
            key,
            customer_index,
            category_code,
            subcategory_code,
            priority_code,
            status_code,
            source_code,
            team_code,
            title,
            description,
        ) in self.TICKETS:
            customer = customers[min(customer_index, len(customers) - 1)]
            category = ComplaintCategory.objects.filter(category_code=category_code, is_deleted=False).first()
            subcategory = ComplaintSubcategory.objects.filter(
                category=category,
                subcategory_code=subcategory_code,
                is_deleted=False,
            ).first() if category else None
            priority = ComplaintPriority.objects.filter(priority_code=priority_code, is_deleted=False).first()
            status = ComplaintStatus.objects.filter(status_code=status_code, is_deleted=False).first()
            source = ComplaintSource.objects.filter(source_code=source_code, is_deleted=False).first()
            team = ComplaintTeam.objects.filter(team_code=team_code, is_deleted=False).first()

            if not all([category, priority, status]):
                self.log(f"Missing master data for {key} - skipping.")
                continue

            location_parts = [
                customer.building_no,
                customer.street,
                customer.area,
                customer.pincode,
            ]
            location_text = ", ".join(part for part in location_parts if part)

            ticket, _ = ComplaintTicket.objects.update_or_create(
                idempotency_key=key,
                defaults={
                    "source": source,
                    "customer": customer,
                    "wa_phone": customer.contact_no,
                    "profile_name": customer.customer_name,
                    "category": category,
                    "subcategory": subcategory,
                    "priority": priority,
                    "status": status,
                    "title": title,
                    "description": description,
                    "location_text": location_text,
                    "latitude": customer.latitude or None,
                    "longitude": customer.longitude or None,
                    "state": customer.state,
                    "district": customer.district,
                    "corporation": customer.corporation,
                    "municipality": customer.municipality,
                    "town_panchayat": customer.town_panchayat,
                    "panchayat_union": customer.panchayat_union,
                    "panchayat": customer.panchayat,
                    "assigned_team": team,
                    "assigned_staff": getattr(team, "lead_staff", None) if team else None,
                    "resolved_at": now if status.status_code in ("RESOLVED", "CLOSED") else None,
                    "closed_at": now if status.status_code == "CLOSED" else None,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            ComplaintStatusHistory.objects.get_or_create(
                ticket=ticket,
                to_status=status,
                remarks=f"Seeded as {status.status_name}",
                defaults={
                    "from_status": None,
                    "changed_by_system": True,
                    "visible_to_citizen": True,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            ComplaintComment.objects.get_or_create(
                ticket=ticket,
                comment_text=f"Seed note: {description}",
                defaults={
                    "comment_by_customer": customer,
                    "is_internal": False,
                    "is_sensitive": False,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            created_or_updated += 1

        self.log(f"---Complaint tickets seeded ({created_or_updated} records)---")
