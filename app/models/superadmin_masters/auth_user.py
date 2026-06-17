from django.db import models
from django.db.models import Q
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

from app.utils.base_models import BaseMaster

from app.utils.comfun import generate_unique_id
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.user_creations.staffcreation import Staffcreation



def generate_user_id():
    return f"SUPUSER-{generate_unique_id()}"

class UserManager(BaseUserManager):
    """
    Custom user manager to support Django's createsuperuser flow.

    We intentionally keep 'username' only strictly required for platform super admins.
    Staff/customer users can still authenticate via the existing business login flow.
    """

    def create_user(self, username=None, password=None, **extra_fields):
        user = self.model(username=username, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Allow system-created users that will set a password later.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        if not username:
            raise ValueError("Superuser must have a username")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_deleted", False)
        extra_fields["is_superuser"] = True  # from PermissionsMixin

        extra_fields["user_type_id"] = None
        extra_fields["staffusertype_id"] = None
        extra_fields["staff_id"] = None
        extra_fields["customer_id"] = None

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(BaseMaster, AbstractBaseUser, PermissionsMixin):


    # -----------------------------
    # Core User Identity
    # -----------------------------
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Required for platform super admins. Staff users may be created without it.",
    )

    email = models.EmailField(
        null=True,
        blank=True,
    )

    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_user_id,
        editable=False,
    )

    user_type_id = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        db_column="user_type_id",
        related_name="users"
    )

    # -----------------------------
    # STAFF-RELATED FIELDS
    # -----------------------------
    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        db_column="staffusertype_id",
        related_name="users_staff_usertype"
    )

    staff_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_staff",
        db_column="staff_id",
        to_field="staff_unique_id"
    )

    # -----------------------------
    # CUSTOMER-RELATED FIELD
    # -----------------------------
    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        related_name="users_customer",
        db_column="customer_id",
        to_field="unique_id"
    )

    # -----------------------------
    # LOCATION FIELDS
    # -----------------------------
    district_id = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        db_column="district_id",
        related_name="users_district"
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        db_column="city_id",
        related_name="users_city"
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        db_column="zone_id",
        related_name="users_zone"
    )

    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        db_column="ward_id",
        related_name="users_ward"
    )

    # -----------------------------
    # SYSTEM FIELDS
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin-site access flag (not a business role).",
    )
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "auth_user"
        ordering = ["-created_at"]
        verbose_name = "User"
        verbose_name_plural = "Users"
        constraints = [
            # Platform super admins must not be attached to any tenant/business identity.
            models.CheckConstraint(
                name="platform_superuser_no_tenant_links",
                check=(
                    Q(is_superuser=False)
                    | (
                        Q(is_superuser=True)
                       
                        & Q(staff_id__isnull=True)
                        & Q(customer_id__isnull=True)
                    )
                ),
            ),
           
        ]

    def __str__(self):
        return self.username or self.unique_id
