from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id



def generate_mainscreentype_id():
    return f"MSCRTYPE-{generate_unique_id()}"


class MainScreenType(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_mainscreentype_id,
        editable=False
    )

    type_name = models.CharField(
        max_length=50,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["type_name"]
        verbose_name = "Main Screen Type"
        verbose_name_plural = "Main Screen Types"

    def __str__(self):
        return self.type_name

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])