from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .mainscreentype import MainScreenType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_mainscreen_id():
    return f"MAINSCREEN-{generate_unique_id()}"


class MainScreen(BaseMaster):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_mainscreen_id,
        editable=False
    )

    mainscreentype_id = models.ForeignKey(
        MainScreenType,
        on_delete=models.PROTECT,
        related_name="mainscreens",
        to_field="unique_id",
        db_column="mainscreentype_id"   
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

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])