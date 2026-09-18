from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.bin_qr import generate_bin_qr_content
from app.models.masters.ward import Ward


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"


class BinType(models.TextChoices):
    SMALL = "small", "Small"
    MEDIUM = "medium", "Medium"
    LARGE = "large", "Large"
   

class Bins(BaseMaster):

    CACHE_SCOPES = ("bins_list", "bins_detail")

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

    country_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bins",
        to_field="unique_id",
        db_column="ward_id",
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
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

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
            cp = self.collection_point_id
            self.country_id = cp.country_id
            self.state_id = cp.state_id
            self.district_id = cp.district_id
            self.area_type_id = cp.area_type_id
            self.corporation_id = cp.corporation_id
            self.municipality_id = cp.municipality_id
            self.town_panchayat_id = cp.town_panchayat_id
            self.panchayat_union_id = cp.panchayat_union_id
            self.panchayat_id = cp.panchayat_id

        is_create = self._state.adding
        super().save(*args, **kwargs)

        if is_create or not self.bin_qr:
            self._regenerate_qr_code()
