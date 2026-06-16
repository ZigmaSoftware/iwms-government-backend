from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward

from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType

from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# min 6 chars, 1 uppercase + 1 lowercase + 1 digit
DEFAULT_CUSTOMER_PASSWORD = "Customer1"

CUSTOMER_DATA = [
    {"customer_name": "Sameer",    "contact_no": "7890123456", "building_no": "12A", "street": "Gamma Road",    "area": "Gamma 1",  "pincode": "600017", "latitude": "13.0826", "longitude": "80.2707", "id_no": "AADHAAR-7890-01"},
    {"customer_name": "Priya",     "contact_no": "7890123457", "building_no": "24B", "street": "Alpha Street",  "area": "Alpha 2",  "pincode": "600018", "latitude": "13.0831", "longitude": "80.2712", "id_no": "AADHAAR-7890-02"},
    {"customer_name": "Ravi",      "contact_no": "7890123458", "building_no": "5C",  "street": "Beta Lane",     "area": "Beta 3",   "pincode": "600019", "latitude": "13.0836", "longitude": "80.2717", "id_no": "AADHAAR-7890-03"},
    {"customer_name": "Kavitha",   "contact_no": "7890123459", "building_no": "33D", "street": "Delta Avenue",  "area": "Delta 1",  "pincode": "600020", "latitude": "13.0841", "longitude": "80.2722", "id_no": "AADHAAR-7890-04"},
    {"customer_name": "Murugan",   "contact_no": "7890123460", "building_no": "7E",  "street": "Epsilon Road",  "area": "Epsilon 2","pincode": "600021", "latitude": "13.0846", "longitude": "80.2727", "id_no": "AADHAAR-7890-05"},
    {"customer_name": "Sangeetha", "contact_no": "7890123461", "building_no": "18F", "street": "Zeta Street",   "area": "Zeta 3",   "pincode": "600022", "latitude": "13.0851", "longitude": "80.2732", "id_no": "AADHAAR-7890-06"},
    {"customer_name": "Vijay",     "contact_no": "7890123462", "building_no": "42G", "street": "Eta Lane",      "area": "Eta 1",    "pincode": "600023", "latitude": "13.0856", "longitude": "80.2737", "id_no": "AADHAAR-7890-07"},
    {"customer_name": "Deepa",     "contact_no": "7890123463", "building_no": "9H",  "street": "Theta Avenue",  "area": "Theta 2",  "pincode": "600024", "latitude": "13.0861", "longitude": "80.2742", "id_no": "AADHAAR-7890-08"},
    {"customer_name": "Arun",      "contact_no": "7890123464", "building_no": "51I", "street": "Iota Road",     "area": "Iota 3",   "pincode": "600025", "latitude": "13.0866", "longitude": "80.2747", "id_no": "AADHAAR-7890-09"},
    {"customer_name": "Meena",     "contact_no": "7890123465", "building_no": "3J",  "street": "Kappa Street",  "area": "Kappa 1",  "pincode": "600026", "latitude": "13.0871", "longitude": "80.2752", "id_no": "AADHAAR-7890-10"},
    {"customer_name": "Suresh",    "contact_no": "7890123466", "building_no": "27K", "street": "Lambda Lane",   "area": "Lambda 2", "pincode": "600027", "latitude": "13.0876", "longitude": "80.2757", "id_no": "AADHAAR-7890-11"},
    {"customer_name": "Divya",     "contact_no": "7890123467", "building_no": "14L", "street": "Mu Avenue",     "area": "Mu 3",     "pincode": "600028", "latitude": "13.0881", "longitude": "80.2762", "id_no": "AADHAAR-7890-12"},
    {"customer_name": "Karthik",   "contact_no": "7890123468", "building_no": "6M",  "street": "Nu Road",       "area": "Nu 1",     "pincode": "600029", "latitude": "13.0886", "longitude": "80.2767", "id_no": "AADHAAR-7890-13"},
    {"customer_name": "Radha",     "contact_no": "7890123469", "building_no": "39N", "street": "Xi Street",     "area": "Xi 2",     "pincode": "600030", "latitude": "13.0891", "longitude": "80.2772", "id_no": "AADHAAR-7890-14"},
    {"customer_name": "Balaji",    "contact_no": "7890123470", "building_no": "22O", "street": "Omicron Lane",  "area": "Omicron 3","pincode": "600031", "latitude": "13.0896", "longitude": "80.2777", "id_no": "AADHAAR-7890-15"},
]


class CustomerCreationSeeder(BaseSeeder):
    name = "customer_creation"

    def run(self):
        country = Country.objects.filter(name="India").first()
        state = State.objects.filter(name="Tamil Nadu").first()
        district = District.objects.filter(name="Chennai").first()
        city = City.objects.filter(name="Chennai City").first()
        zone = Zone.objects.filter(zone_name="Zone 1").first()
        ward = Ward.objects.filter(ward_name="Ward 1").first()

        if not all([country, state, district, city, zone, ward]):
            self.log("Required location hierarchy missing.")
            return

        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(sub_property_name="Apartment", is_deleted=False).first()

        if not property_obj or not sub_property_obj:
            self.log("Required property/sub-property missing.")
            return

        company = Company.objects.filter(is_deleted=False).first()
        project = Project.objects.filter(company_id=company, is_deleted=False).first() if company else None

        customer_type = UserType.objects.filter(name__iexact="customer").first()
        if not customer_type:
            self.log("UserType 'customer' missing. Seed role-assign before customers.")
            return

        UserModel = get_user_model()

        now = timezone.now()
        for entry in CUSTOMER_DATA:
            hashed_password = make_password(DEFAULT_CUSTOMER_PASSWORD)
            customer, created = CustomerCreation.objects.get_or_create(
                customer_name=entry["customer_name"],
                contact_no=entry["contact_no"],
                defaults={
                    "username": entry["contact_no"],
                    "password": hashed_password,
                    "password_crt_date": now,
                    "building_no": entry["building_no"],
                    "street": entry["street"],
                    "area": entry["area"],
                    "ward": ward,
                    "zone": zone,
                    "city": city,
                    "district": district,
                    "state": state,
                    "country": country,
                    "pincode": entry["pincode"],
                    "latitude": entry["latitude"],
                    "longitude": entry["longitude"],
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": entry["id_no"],
                    "property_ref": property_obj,
                    "sub_property": sub_property_obj,
                    "company_id": company,
                    "project_id": project,
                    "user_type_id": customer_type,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Exists"
            self.log(f"Customer {action}: {customer.customer_name}")
            UserModel.objects.filter(customer_id_id=customer.unique_id).delete()

        self.log(f"---Customers seeded ({len(CUSTOMER_DATA)} records)---")
