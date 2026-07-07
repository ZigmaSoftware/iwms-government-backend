from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_ticket.language_master import ComplaintLanguage


class ComplaintLanguageSeeder(BaseSeeder):
    name = "complaint_language"

    # (language_code, language_name, is_default)
    LANGUAGES = [
        ("en", "English", True),
        ("ta", "Tamil", False),
        ("hi", "Hindi", False),
    ]

    def run(self):
        for code, name, is_default in self.LANGUAGES:
            ComplaintLanguage.objects.get_or_create(
                language_code=code,
                defaults={
                    "language_name": name,
                    "is_default": is_default,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        self.log(f"---Complaint languages seeded ({len(self.LANGUAGES)} records)---")
