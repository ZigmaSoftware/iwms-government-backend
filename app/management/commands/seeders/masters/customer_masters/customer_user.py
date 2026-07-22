from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.role_management.userType import UserType
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty


class CustomerUserSeeder(BaseSeeder):
    """Create a ready-to-login mobile citizen (`Sameer` / `Customer1`).

    Customer login (`login/` with the customer provider) needs a "customer"
    UserType and a CustomerCreation row that carries a username + password. The
    stock customer seeder leaves username/password blank, so no citizen can log
    in. This seeder wires one up in a panchayat that is actively serviced
    (Modakkurichi — the same trip driver_user runs).
    """

    name = "CustomerUserSeeder"

    USERNAME = "Sameer"
    PASSWORD = "Customer1"
    PANCHAYAT_NAME = "Modakkurichi Panchayat"

    def run(self):
        # Customer login builds its permission payload against a "customer" UserType.
        user_type, _ = UserType.objects.get_or_create(
            name="Customer",
            defaults={"is_active": True, "is_deleted": False},
        )

        property_obj = Property.objects.filter(
            property_name="Residential", is_deleted=False
        ).first()
        sub_property = (
            SubProperty.objects.filter(
                property_id=property_obj,
                sub_property_name="Apartment",
                is_deleted=False,
            ).first()
            if property_obj
            else None
        )
        if not property_obj or not sub_property:
            self.log("Property/SubProperty not found — run PropertySeeder first. Skipping.")
            return

        panchayat = (
            Panchayat.objects.filter(panchayat_name=self.PANCHAYAT_NAME, is_deleted=False)
            .select_related("district_id", "state_id", "area_type_id")
            .first()
        )
        if not panchayat:
            self.log(f"No panchayat '{self.PANCHAYAT_NAME}' — run geo seeders first. Skipping.")
            return

        customer, created = CustomerCreation.objects.get_or_create(
            username=self.USERNAME,
            defaults={
                "customer_name": "Sameer",
                "contact_no": "9000000001",
                "building_no": "1",
                "street": "Demo Street",
                "area": "Modakkurichi",
                "state": panchayat.state_id,
                "district": panchayat.district_id,
                "area_type": panchayat.area_type_id,
                "panchayat": panchayat,
                "pincode": "638104",
                "latitude": "11.3805",
                "longitude": "77.7032",
                "id_proof_type": "AADHAAR",
                "id_no": "SAMEER-CUST-0001",
                "property_ref": property_obj,
                "sub_property": sub_property,
                "password": make_password(self.PASSWORD),
                "is_active": True,
                "is_deleted": False,
            },
        )
        if not created:
            customer.customer_name = "Sameer"
            customer.password = make_password(self.PASSWORD)
            customer.state = panchayat.state_id
            customer.district = panchayat.district_id
            customer.area_type = panchayat.area_type_id
            customer.panchayat = panchayat
            customer.property_ref = property_obj
            customer.sub_property = sub_property
            customer.is_active = True
            customer.is_deleted = False
            customer.save()

        self.log(
            f"{'Created' if created else 'Updated'} customer login: "
            f"{self.USERNAME} / {self.PASSWORD} ({customer.unique_id})"
        )
