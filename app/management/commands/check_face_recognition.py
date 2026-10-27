"""Deployment preflight for the configured attendance face provider."""
from django.core.management.base import BaseCommand, CommandError

from app.services.face_recognition import get_provider


class Command(BaseCommand):
    help = "Load the configured face provider and fail if registration is unavailable."

    def handle(self, *args, **options):
        provider = get_provider()
        ready, error = provider.health()
        if not ready:
            raise CommandError(f"Face provider {provider.name} is unavailable: {error}")
        self.stdout.write(self.style.SUCCESS(f"Face provider {provider.name} ready"))
