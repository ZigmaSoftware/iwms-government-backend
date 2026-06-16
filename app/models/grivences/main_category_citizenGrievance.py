from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_maincategory_id():
    return f"CMPMC-{generate_unique_id()}"

class MainCategory(BaseMaster):
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
        default=generate_maincategory_id,
        editable=False
    )

    main_categoryName = models.CharField(
        max_length=100,
        unique=True,
    )

    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Main Category"
        verbose_name_plural = "Main Categories"

    def __str__(self):
        return self.main_categoryName

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
