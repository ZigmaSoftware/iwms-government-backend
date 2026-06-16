from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType


def generate_block_panchayat_union_id():
    return f"BLKPU-{generate_unique_id()}"


class BlockPanchayatUnion(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_block_panchayat_union_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="block_panchayat_unions",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="block_panchayat_unions",
        db_column="project_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="block_panchayat_unions",
        db_column="state_id",
    )
    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="block_panchayat_unions",
        db_column="district_id",
    )

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        limit_choices_to={"name": "Rural"},
        null=True,
        blank=True,
    )
    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Block Panchayat Union"},
        null=True,
        blank=True,
    )

    block_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["block_name"]
