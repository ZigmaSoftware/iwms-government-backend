from django.urls import reverse
from django.views.generic import TemplateView
from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType


class CitizenLoginPage(TemplateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_types"] = list(
            UserType.objects.filter(is_active=True, is_deleted=False).order_by("name")
        )
        context["customers"] = list(
            CustomerCreation.objects.filter(is_active=True, is_deleted=False)
            .order_by("customer_name")
            .values("customer_name", "contact_no")[:80]
        )
        context["login_path"] = reverse("customer-login-list")
        return context
