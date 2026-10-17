from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_subcategory_id():
    return f"CPTSUB-{generate_unique_id()}"


class ComplaintSubcategory(BaseMaster):
    """Subcategories under a complaint category."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    category_id = models.CharField(max_length=30)
    subcategory_code = models.CharField(max_length=80)
    subcategory_name = models.CharField(max_length=150)
    default_priority_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Subcategory"
        verbose_name_plural = "Complaint Subcategories"
        unique_together = ("category_id", "subcategory_code")

    def __str__(self):
        return self.subcategory_name

    def _lookup(self, model_path, value):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, "unique_id")

    @property
    def category(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.category_master.ComplaintCategory",
            self.category_id,
        )

    @property
    def default_priority(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.priority_master.ComplaintPriority",
            self.default_priority_id,
        )

    @property
    def tickets(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        return ComplaintTicket.objects.filter(subcategory_id=self.unique_id)
