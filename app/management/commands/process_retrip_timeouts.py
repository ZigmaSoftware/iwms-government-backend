from django.core.management.base import BaseCommand

from app.services.retrip_timeout_service import process_retrip_timeouts


class Command(BaseCommand):
    help = "Send Re-Trip reminders and expire requests past their decision window."

    def handle(self, *args, **options):
        result = process_retrip_timeouts()
        self.stdout.write(
            self.style.SUCCESS(
                "Re-Trip timeouts processed: "
                f"{result['reminded']} reminded, "
                f"{result['escalated']} escalated, "
                f"{result['expired']} expired."
            )
        )
