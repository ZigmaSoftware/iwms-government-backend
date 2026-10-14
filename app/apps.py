from django.apps import AppConfig
from django.db.models.signals import post_migrate


# class ApiConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'app'



class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        import app.signals.permission_signals  # Register signals on app startup
        import app.signals.trip_plan_signals  # Register transport plan signals

        def sync_userscreen_columns_after_migrate(sender, **kwargs):
            if sender.name != self.name:
                return
            try:
                from app.services.schema_sync_service import sync_all_screens
                sync_all_screens()
            except Exception:
                pass

        post_migrate.connect(
            sync_userscreen_columns_after_migrate,
            sender=self,
            dispatch_uid="app.sync_userscreen_columns_after_migrate",
        )
