from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.bin_qr import generate_bin_qr_content
from app.models.masters.ward import Ward
from app.utils import ref_cache


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




    # Collection_point / Ward / WasteType are plain unique_id strings (no DB
    # relation); the `collection_point` / `ward` / `wastetype` properties
    # below resolve them.
    collection_point_id = models.CharField(
        max_length=30, db_column="collection_point_id", db_index=True
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
    ward_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="ward_id", db_index=True
    )

    wastetype_id = models.CharField(max_length=100, db_column="wastetype_id", db_index=True)

    bin_name = models.CharField(max_length=100)
    bin_capacity = models.IntegerField()
    bin_type = models.CharField(max_length=10, choices=BinType.choices)
    bin_image = models.CharField(max_length=100)
    bin_qr = models.ImageField(upload_to="bin_qr/", blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _lookup(self, model, value):
        """Resolve a plain unique_id into its row (request-cached)."""
        return ref_cache.get(model, value)

    @property
    def collection_point(self):
        return self._lookup(Collection_point, self.collection_point_id)

    @property
    def ward(self):
        return self._lookup(Ward, self.ward_id)

    @property
    def wastetype(self):
        return self._lookup(WasteType, self.wastetype_id)

    def _regenerate_qr_code(self):
        file_content = generate_bin_qr_content(self.unique_id)
        file_name = f"{self.unique_id}.png"
        if self.bin_qr:
            self.bin_qr.delete(save=False)
        self.bin_qr.save(file_name, file_content, save=False)
        super().save(update_fields=["bin_qr"])

    def save(self, *args, **kwargs):
        cp = self.collection_point
        if cp:
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
