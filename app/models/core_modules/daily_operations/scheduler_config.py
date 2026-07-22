from datetime import time as datetime_time

from django.db import models


class SchedulerConfig(models.Model):
    run_time = models.TimeField(
        default=datetime_time(4, 0),
        help_text="Daily trip generation time in IST (HH:MM)",
    )
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduler_config"

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
