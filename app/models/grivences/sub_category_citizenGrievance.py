from django.db import models
from app.utils.base_models import BaseMaster
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.utils.comfun import generate_unique_id



def generate_subcategory_id():
    return f"CMPSC-{generate_unique_id()}"


class SubCategory(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    mainCategory = models.ForeignKey(
        MainCategory,
        on_delete=models.PROTECT,
        related_name='sub_categories'
    )

    name = models.CharField(max_length=120)
    class Meta:
        ordering = ["unique_id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
