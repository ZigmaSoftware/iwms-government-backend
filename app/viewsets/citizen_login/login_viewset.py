from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token as AuthToken

from django.contrib.auth.hashers import check_password
from django.db.models import Q

from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType
from app.serializers.citizenLogin.login_serializer import LoginSerializer


class CitizenLoginViewSet(viewsets.ViewSet):
    serializer_class = LoginSerializer

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    @staticmethod
    def _password_matches(stored_password, raw_password):
        if not stored_password:
            return False
        try:
            return check_password(raw_password, stored_password)
        except (ValueError, TypeError):
            return stored_password == raw_password

    @staticmethod
    def _build_permission_payload(user_type):
        queryset = (
            user_type.user_permissions.filter(is_active=True, is_deleted=False)
            .select_related("main_screen", "user_screen")
        )
        permissions = []
        for perm in queryset:
            permissions.append(
                {
                    "id": perm.id,
                    "unique_id": perm.unique_id,
                    "main_screen_id": perm.main_screen_id,
                    "main_screen_unique_id": perm.main_screen.unique_id if perm.main_screen else None,
                    "main_screen_name": perm.main_screen.mainscreen if perm.main_screen else None,
                    "user_screen_id": perm.user_screen_id,
                    "user_screen_unique_id": perm.user_screen.unique_id if perm.user_screen else None,
                    "user_screen_name": perm.user_screen.screen_name if perm.user_screen else None,
                    "permissions": perm.permissions or {},
                }
            )
        return permissions

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Invalid payload", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_type_identifier = serializer.validated_data["user_type"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user_type = UserType.objects.filter(
            Q(name__iexact=user_type_identifier) | Q(unique_id__iexact=user_type_identifier),
            is_active=True,
            is_deleted=False,
        ).first()
        print(user_type)

        if not user_type:
            return Response(
                {"status": False, "message": "Unknown user type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up customer by contact_no or customer_name with the user_type
        customer = CustomerCreation.objects.filter(
            Q(contact_no__iexact=username) | Q(customer_name__iexact=username),
            is_active=True,
            is_deleted=False,
            user_type=user_type,
        ).first()

        if not customer:
            return Response(
                {"status": False, "message": "Customer record not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Use CustomerCreation password directly (no Django User needed)
        if not self._password_matches(customer.password, password):
            return Response(
                {"status": False, "message": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create or get token for the customer (use customer unique_id as username)
        token, _ = AuthToken.objects.get_or_create(key=customer.unique_id)
        user_type_payload = {
            "id": user_type.id,
            "unique_id": user_type.unique_id,
            "name": user_type.name,
        }

        return Response(
            {
                "status": True,
                "message": "Login successful",
                "token": token.key,
                "user_type": user_type_payload,
                "permissions": self._build_permission_payload(user_type),
                "user": {
                    "unique_id": customer.unique_id,
                    "username": customer.contact_no,
                    "email": customer.email,
                    "first_name": customer.customer_name,
                },
            },
            status=status.HTTP_200_OK,
        )

    def list(self, request):
        user_types = list(
            UserType.objects.filter(is_active=True, is_deleted=False)
            .order_by("name")
            .values("id", "unique_id", "name")
        )
        customers = list(
            CustomerCreation.objects.filter(
                is_active=True,
                is_deleted=False,
            )
            .order_by("customer_name")
            .values("customer_name", "contact_no")[:80]
        )
        return Response(
            {
                "status": True,
                "message": "Login metadata",
                "user_types": user_types,
                "customers": customers,
            },
            status=status.HTTP_200_OK,
        )
