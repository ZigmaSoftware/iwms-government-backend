from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from django.core.exceptions import ValidationError

def geneate_collection_point_id():
    return f"CP-{generate_unique_id()}"

class Collection_point(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_collection_point_id,
        editable=False
    )

    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.PROTECT,
        related_name="collection_points",
        to_field="unique_id",
        db_column="location_node_id",
    )

    cp_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    coordinates = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    def clean(self):
        if not self.location_node_id:
            raise ValidationError("Collection Point must belong to a hierarchy node.")
        

    def __str__(self):
        return f"{self.cp_name} ({self.location_node})" if self.location_node_id else self.cp_name
