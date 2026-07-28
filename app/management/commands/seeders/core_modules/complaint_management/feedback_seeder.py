from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.feedback import ComplaintFeedback
from app.models.core_modules.complaint_management.ticket import ComplaintTicket


class ComplaintFeedbackSeeder(BaseSeeder):
    name = "complaint_feedback"

    FEEDBACK = {
        "seed-address-change-001": (5, "Address change was handled quickly.", True),
        "seed-worker-conduct-001": (4, "Supervisor followed up and closed the issue.", True),
    }

    def run(self):
        total = 0
        for key, (rating, text, solved) in self.FEEDBACK.items():
            ticket = ComplaintTicket.objects.filter(idempotency_key=key, is_deleted=False).first()
            if not ticket:
                self.log(f"Ticket '{key}' not found - skipping feedback.")
                continue

            ComplaintFeedback.objects.update_or_create(
                ticket=ticket,
                defaults={
                    "customer": ticket.customer,
                    "rating": rating,
                    "feedback_text": text,
                    "is_issue_solved": solved,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            total += 1

        self.log(f"---Complaint feedback seeded ({total} records)---")
