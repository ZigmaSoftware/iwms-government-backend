from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_category_id():
    return f"CPTCAT-{generate_unique_id()}"


class ComplaintCategory(BaseMaster):
    """Top-level complaint categories (Missed Pickup, Change Address, ...)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_category_id,
        editable=False,
    )

    module_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    category_code = models.CharField(max_length=80, unique=True)
    category_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    default_priority_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    default_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    requires_location = models.BooleanField(default=True)
    requires_media = models.BooleanField(default=False)
    requires_address_change_detail = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Category"
        verbose_name_plural = "Complaint Categories"

    def __str__(self):
        return self.category_name

    def _lookup(self, model_path, value):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, "unique_id")

    @property
    def module(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.module_master.ComplaintModule",
            self.module_id,
        )

    @property
    def default_priority(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.priority_master.ComplaintPriority",
            self.default_priority_id,
        )

    @property
    def default_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.default_team_id,
        )

    @property
    def subcategories(self):
        from app.models.core_modules.complaint_management.subcategory_master import (
            ComplaintSubcategory,
        )

        return ComplaintSubcategory.objects.filter(category_id=self.unique_id)

    @property
    def tickets(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        return ComplaintTicket.objects.filter(category_id=self.unique_id)
