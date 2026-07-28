from django.contrib import admin

from app.models.superadmin.user_management.staffcreation import Staffcreation, StaffPersonalDetails
from app.models.masters.customer_masters.customercreation import CustomerCreation


@admin.register(Staffcreation)
class StaffcreationAdmin(admin.ModelAdmin):
    list_display = ("staff_unique_id", "emp_id", "employee_name", "username", "office_email", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted", "is_staff")
    search_fields = ("employee_name", "username", "email", "staff_unique_id")
    ordering = ("-created_at",)


@admin.register(StaffPersonalDetails)
class StaffPersonalDetailsAdmin(admin.ModelAdmin):
    list_display = ("staff_unique_id", "staff", "contact_mobile", "contact_email")
    search_fields = ("staff__employee_name", "contact_mobile")
    ordering = ("-created_at",)


@admin.register(CustomerCreation)
class CustomerCreationAdmin(admin.ModelAdmin):
    list_display = ("unique_id", "customer_name", "contact_no", "username", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("customer_name", "contact_no", "username")
    ordering = ("customer_name",)
