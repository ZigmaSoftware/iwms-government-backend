from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


# min 6 chars, 1 uppercase + 1 lowercase + 1 digit — same convention as CustomerUserSeeder
DEFAULT_CUSTOMER_PASSWORD = "Customer1"


class CustomerCreationSeeder(BaseSeeder):
    name = "CustomerCreationSeeder"

    # (customer_name, contact_no, building_no, street, area, pincode, lat, lon, id_proof_type, id_no, is_bulk, panchayat_name)
    CUSTOMERS = [
        ("Murugan Pillai",   "9876543210", "12A", "Gandhi Street",   "Erode Town", "638001", "11.341", "77.717", "AADHAAR",  "1234 5678 9012", False, "Anthiyur Panchayat"),
        ("Selvi Durai",      "9876543211", "45B", "Anna Nagar",      "Salem",      "636007", "11.667", "78.146", "VOTER_ID", "TN123456789", False, "Bhavani Panchayat"),
        ("Karthikeyan R",    "9876543212", "78C", "Nehru Road",      "Coimbatore", "641001", "11.017", "76.955", "PAN_CARD", "ABCDE1234F", True, "Gobichettipalayam Panchayat"),
        ("Vasantha Kumari",  "9876543213", "21D", "Raja Street",     "Chennai",    "600001", "13.082", "80.270", "AADHAAR",  "9876 5432 1098", True, "Kavundampalayam Panchayat"),
        ("Periasamy S",      "9876543214", "63E", "Meenakshi Nagar", "Madurai",    "625001", "9.9252", "78.119", "VOTER_ID", "TN987654321", False, "Modakkurichi Panchayat"),
        # --- Anthiyur Panchayat household-assignment fill (driver_user demo trip) ---
        # Lat/long clustered around the real Anthiyur Panchayat centroid (11.3410, 77.5820)
        # used elsewhere in the seeders (see schedule_masters/collection_point.py CP-Anthiyur-PLB-01).
        ("Chinnasamy K",     "9876543215", "5A",  "Bazaar Street",    "Anthiyur", "638501", "11.3395", "77.5808", "AADHAAR",  "AADHAAR-9001-01", False, "Anthiyur Panchayat"),
        ("Lakshmi Ammal",    "9876543216", "17B", "Kovil Street",     "Anthiyur", "638501", "11.3421", "77.5834", "AADHAAR",  "AADHAAR-9001-02", False, "Anthiyur Panchayat"),
        ("Rajendran P",      "9876543217", "29C", "Market Road",      "Anthiyur", "638501", "11.3403", "77.5841", "VOTER_ID", "TN900000103",      False, "Anthiyur Panchayat"),
        ("Kalaivani S",      "9876543218", "8D",  "Perumal Kovil St", "Anthiyur", "638501", "11.3432", "77.5812", "AADHAAR",  "AADHAAR-9001-04", False, "Anthiyur Panchayat"),
        ("Muthusamy V",      "9876543219", "41E", "Mill Road",        "Anthiyur", "638501", "11.3388", "77.5825", "AADHAAR",  "AADHAAR-9001-05", False, "Anthiyur Panchayat"),
        ("Ponnammal R",      "9876543220", "3F",  "Cauvery Street",   "Anthiyur", "638501", "11.3417", "77.5798", "VOTER_ID", "TN900000106",      False, "Anthiyur Panchayat"),
        ("Dhandapani M",     "9876543221", "22G", "New Bus Stand Rd", "Anthiyur", "638501", "11.3409", "77.5847", "AADHAAR",  "AADHAAR-9001-07", False, "Anthiyur Panchayat"),
        ("Shanthi K",        "9876543222", "14H", "Agraharam Street", "Anthiyur", "638501", "11.3440", "77.5820", "AADHAAR",  "AADHAAR-9001-08", False, "Anthiyur Panchayat"),
        ("Govindasamy N",    "9876543223", "36I", "Vellode Road",     "Anthiyur", "638501", "11.3381", "77.5809", "PAN_CARD", "ANTHI9001I",       False, "Anthiyur Panchayat"),
        ("Meenakshi P",      "9876543224", "9J",  "Railway Feeder Rd","Anthiyur", "638501", "11.3424", "77.5788", "AADHAAR",  "AADHAAR-9001-10", False, "Anthiyur Panchayat"),
    ]

    def run(self):
        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property = SubProperty.objects.filter(
            property_id=property_obj, sub_property_name="Apartment", is_deleted=False
        ).first() if property_obj else None

        if not property_obj or not sub_property:
            self.log("Property/SubProperty not found — run PropertySeeder first.")
            return

        count = 0
        for idx, (
            cust_name, contact, building_no, street, area,
            pincode, lat, lon, id_proof_type, id_no, is_bulk, panchayat_name
        ) in enumerate(self.CUSTOMERS):
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name,
                is_deleted=False,
            ).select_related("district_id", "state_id", "area_type_id").first()

            if not panchayat:
                self.log(f"No panchayat '{panchayat_name}' for {cust_name} — run geo seeders first. Skipping.")
                continue

            _, created = CustomerCreation.objects.update_or_create(
                id_no=id_no,
                defaults={
                    "customer_name": cust_name,
                    "contact_no": contact,
                    "username": contact,
                    "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                    "building_no": building_no,
                    "street": street,
                    "area": area,
                    "state": panchayat.state_id,
                    "district": panchayat.district_id,
                    "area_type": panchayat.area_type_id,
                    "panchayat": panchayat,
                    "pincode": pincode,
                    "latitude": lat,
                    "longitude": lon,
                    "id_proof_type": id_proof_type,
                    "property_ref": property_obj,
                    "sub_property": sub_property,
                    "is_bulkwaste_generator": is_bulk,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1
                self.log(f"Created customer: {cust_name}")
            else:
                self.log(f"Updated customer: {cust_name}")

        self.log(f"---Customers seeded ({count} created)---")
