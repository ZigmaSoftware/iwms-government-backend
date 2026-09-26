from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache



def generate_mainscreen_id():
    return f"MAINSCREEN-{generate_unique_id()}"


class MainScreen(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_mainscreen_id,
        editable=False
    )

    mainscreentype_id = models.CharField(
        max_length=30,
        db_column="mainscreentype_id",
        db_index=True,
    )

    mainscreen_name = models.CharField(max_length=50, unique=True)
    icon_name = models.CharField(max_length=50, unique=True)
    order_no = models.IntegerField()

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no"]
        verbose_name = "Main Screen"
        verbose_name_plural = "Main Screens"
        constraints = [
            models.UniqueConstraint(
                fields=["mainscreentype_id", "order_no"],
                name="unique_order_per_mainscreentype"
            )
        ]

    def __str__(self):
        return self.mainscreen_name

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def mainscreentype(self):
        return self._lookup("app.models.superadmin.screen_management.mainscreentype.MainScreenType", self.mainscreentype_id)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])