"""Close web login sessions whose browser never reported the logout.

A tab closed (or a machine put to sleep) mid-session never calls the logout
API, so its LoginAudit row would stay open. Celery beat runs the same sweep
every 5 minutes (CELERY_BEAT_SCHEDULE "close-idle-login-sessions"); this
command runs it on demand.
"""

from django.core.management.base import BaseCommand

from app.services.login_session import close_stale_sessions


class Command(BaseCommand):
    help = "Stamp logout time on idle / expired web login sessions."

    def handle(self, *args, **options):
        closed = close_stale_sessions()
        self.stdout.write(self.style.SUCCESS(f"Closed {closed} stale login session(s)."))
