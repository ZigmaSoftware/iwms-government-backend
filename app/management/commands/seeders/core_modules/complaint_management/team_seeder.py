from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.complaint_management.team_master import ComplaintTeam


class ComplaintTeamSeeder(BaseSeeder):
    name = "complaint_team"

    # (team_code, team_name, escalation_level, escalates_to_code)
    TEAMS = [
        ("SANITATION", "Sanitation Operations", 1, None),
        ("SANITATION_L2", "Sanitation Supervisor Desk", 2, None),
        ("BILLING", "Billing & Charges", 1, None),
        ("ADDRESS_DESK", "Address & Records Desk", 1, None),
        ("GENERAL", "General Grievance Desk", 1, None),
    ]

    def run(self):
        created = {}
        for code, name, level, _ in self.TEAMS:
            team, _created = ComplaintTeam.objects.get_or_create(
                team_code=code,
                defaults={
                    "team_name": name,
                    "escalation_level": level,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            created[code] = team

        # Wire escalation chain: SANITATION -> SANITATION_L2
        sanitation = created.get("SANITATION")
        sanitation_l2 = created.get("SANITATION_L2")
        if sanitation and sanitation_l2 and not sanitation.escalates_to_id:
            sanitation.escalates_to = sanitation_l2
            sanitation.save(update_fields=["escalates_to"])

        self.log(f"---Complaint teams seeded ({len(self.TEAMS)} records)---")
