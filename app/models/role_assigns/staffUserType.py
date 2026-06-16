from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_staff_usertype_id():
    return f"STUSRTYPE-{generate_unique_id()}"


class StaffUserType(BaseMaster):
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

    STAFF_ROLE_CHOICES = [
        ("company_admin", "Company Admin"),
        ("company_operator", "Company Operator"),
        ("company_driver", "Company Driver"),
        ("company_supervisor", "Company Supervisor"),
        # ("superadmin", "Superadmin"),
        ("company_user", "Company User"),
        ("company_project_admin", "Company Project Admin"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_staff_usertype_id,
        editable=False
    )

    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="staffusertypes",
        to_field="unique_id"
    )

    name = models.CharField(
        max_length=50,
        choices=STAFF_ROLE_CHOICES
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Staff User Type"
        verbose_name_plural = "Staff User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_staff_role_per_usertype_not_deleted"
            )
        ]

    def __str__(self):
        return f"{self.usertype_id.name} → {self.name}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])