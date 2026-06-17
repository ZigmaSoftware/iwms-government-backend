from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.schedule_masters.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.bin_qr import generate_bin_qr_content


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"


class BinType(models.TextChoices):
    SMALL = "small", "Small"
    MEDIUM = "medium", "Medium"
    LARGE = "large", "Large"
   

class Bins(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_id,
        editable=False
    )




    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="collection_point_id"
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="district_id",
        null=True,
        blank=True
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="city_id",
        null=True,
        blank=True
    )

    wastetype_id = models.ForeignKey(
        WasteType,  
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="wastetype_id"
    )

    bin_name = models.CharField(max_length=100)
    bin_capacity = models.IntegerField()
    bin_type = models.CharField(max_length=10, choices=BinType.choices)
    bin_image = models.CharField(max_length=100)
    bin_qr = models.ImageField(upload_to="bin_qr/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _regenerate_qr_code(self):
        file_content = generate_bin_qr_content(self.unique_id)
        file_name = f"{self.unique_id}.png"
        if self.bin_qr:
            self.bin_qr.delete(save=False)
        self.bin_qr.save(file_name, file_content, save=False)
        super().save(update_fields=["bin_qr"])

    def save(self, *args, **kwargs):
        if self.collection_point_id:
            self.district_id = self.collection_point_id.district_id
            self.city_id = self.collection_point_id.city_id

        is_create = self._state.adding
        super().save(*args, **kwargs)

        if is_create or not self.bin_qr:
            self._regenerate_qr_code()
