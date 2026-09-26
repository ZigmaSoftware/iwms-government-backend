from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType
from app.utils import ref_cache


def generate_block_panchayat_union_id():
    return f"BLKPU-{generate_unique_id()}"


class BlockPanchayatUnion(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_block_panchayat_union_id,
        editable=False,
    )


    state_id = models.CharField(max_length=30)
    district_id = models.CharField(max_length=30)

    # Plain AreaType / AdministrativeHierarchy unique_ids (no DB relation).
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    hierarchy_id = models.CharField(max_length=30, null=True, blank=True)

    @property
    def area_type(self):
        if not self.area_type_id:
            return None
        return ref_cache.get(AreaType, self.area_type_id)

    @property
    def hierarchy(self):
        if not self.hierarchy_id:
            return None
        return ref_cache.get(AdministrativeHierarchy, self.hierarchy_id)

    block_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["block_name"]
