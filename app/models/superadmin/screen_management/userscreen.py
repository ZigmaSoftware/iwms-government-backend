from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.model_mapper import resolve_userscreen_model
from app.utils import ref_cache



def generate_userscreen_id():
    return f"USERSCREEN-{generate_unique_id()}"


class UserScreen(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_userscreen_id,
        editable=False
    )

    mainscreen_id = models.CharField(
        max_length=30,
        db_column="mainscreen_id",
        db_index=True,
    )

    userscreen_name = models.CharField(max_length=50, unique=True)
    folder_name = models.CharField(max_length=50, unique=True)
    icon_name = models.CharField(max_length=50, unique=True)
    
    # =====================================================
    # DYNAMIC MODEL MAPPING
    # =====================================================

    model_app_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Django app label. Example: hrms"
    )

    model_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Django model name. Example: StaffcreationOfficeDetails"
    )

    # =====================================================

    # REMOVE unique=True
    order_no = models.IntegerField()

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    class Meta:
        ordering = ["order_no"]
        verbose_name = "User Screen"
        verbose_name_plural = "User Screens"
        constraints = [
            models.UniqueConstraint(
                fields=["mainscreen_id", "order_no"],
                name="unique_order_per_mainscreen"
            ),
        ]

    def __str__(self):
        return self.userscreen_name

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def mainscreen(self):
        return self._lookup("app.models.superadmin.screen_management.mainscreen.MainScreen", self.mainscreen_id)

    # =====================================================
    # OPTIONAL HELPER
    # =====================================================

    @property
    def django_model_class(self):
        return resolve_userscreen_model(self)
