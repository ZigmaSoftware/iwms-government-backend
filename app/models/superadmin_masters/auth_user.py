from django.db import models
from django.db.models import Q
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

from app.utils.base_models import BaseMaster

from app.utils.comfun import generate_unique_id
from app.utils import ref_cache



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

    user_type_id = models.CharField(
        max_length=30,
        db_column="user_type_id",
        db_index=True,
        null=True,
        blank=True,
    )

    # -----------------------------
    # STAFF-RELATED FIELDS
    # -----------------------------
    staffusertype_id = models.CharField(
        max_length=30,
        db_column="staffusertype_id",
        db_index=True,
        null=True,
        blank=True,
    )

    staff_id = models.CharField(
        max_length=30,
        db_column="staff_id",
        db_index=True,
        null=True,
        blank=True,
    )

    # -----------------------------
    # CUSTOMER-RELATED FIELD
    # -----------------------------
    customer_id = models.CharField(
        max_length=30,
        db_column="customer_id",
        db_index=True,
        null=True,
        blank=True,
    )

    # -----------------------------
    # LOCATION FIELDS
    # -----------------------------
    # Plain CharField holding District.unique_id (no DB relation/join) —
    # matches the rest of the geo-hierarchy refactor's convention.
    district_id = models.CharField(max_length=30, null=True, blank=True)

    # Dynamic geography: the hierarchy node this user is scoped to. Replaces
    # the static district_id (kept temporarily for zero-downtime migration).
    location_node_id = models.CharField(
        max_length=30,
        db_column="location_node_id",
        db_index=True,
        null=True,
        blank=True,
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

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def user_type(self):
        return self._lookup("app.models.superadmin.role_management.userType.UserType", self.user_type_id)

    @property
    def staffusertype(self):
        return self._lookup("app.models.superadmin.role_management.staffUserType.StaffUserType", self.staffusertype_id)

    @property
    def staff(self):
        return self._lookup("app.models.superadmin.staff_management.staffcreation.Staffcreation", self.staff_id, field="staff_unique_id")

    @property
    def customer(self):
        return self._lookup("app.models.masters.customer_masters.customercreation.CustomerCreation", self.customer_id)

    @property
    def location_node(self):
        return self._lookup("app.models.masters.hierarchy_tree.HierarchyNode", self.location_node_id)
