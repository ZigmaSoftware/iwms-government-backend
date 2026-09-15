from django.db import models
from django.conf import settings

from app.utils.cascade_delete import cascade_soft_delete




class Account(models.Model):

    # Use string primary key
    account_id = models.CharField(
        max_length=50,
        primary_key=True,
        editable=False
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    staff = models.OneToOneField(
        "app.StaffcreationOfficeDetails",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        # Auto assign account_id from related model
        if self.user:
            self.account_id = self.user.unique_id
        elif self.staff:
            self.account_id = self.staff.staff_unique_id

        super().save(*args, **kwargs)


class BaseMaster(models.Model):
    """Shared active/deleted flags for most tables."""
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # Reverse-relation names (related_name strings) to soft-delete
    # transitively when this row is soft-deleted. See app/utils/cascade_delete.py.
    CASCADE_SOFT_DELETE = ()

    created_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created"
    )

    updated_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


    def delete(self, *args, updated_by=None, **kwargs):
        cascade_soft_delete(self, updated_by=updated_by)