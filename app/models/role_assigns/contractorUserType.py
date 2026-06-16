from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_contractor_usertype_id():
    return f"CNTUSRTYPE-{generate_unique_id()}"


class ContractorUserType(BaseMaster):
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

    CONTRACTOR_ROLE_CHOICES = [
        ("contractor_admin", "Contractor Admin"),
        ("contractor_supervisor", "Contractor Supervisor"),
        ("contractor_operator", "Contractor Operator"),
        ("contractor_worker", "Contractor Worker"),
        ("contractor_driver", "Contractor Driver"),
    ]

    unique_id = models.CharField(
        max_length=35,
        primary_key=True,
        unique=True,
        default=generate_contractor_usertype_id,
        editable=False,
    )

    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="contractorusertypes",
        to_field="unique_id",
    )

    name = models.CharField(
        max_length=50,
        choices=CONTRACTOR_ROLE_CHOICES,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Contractor User Type"
        verbose_name_plural = "Contractor User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_contractor_role_per_usertype_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.usertype_id.name} → {self.name}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
