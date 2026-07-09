from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class CustomerCreationSeeder(BaseSeeder):
    name = "CustomerCreationSeeder"

    # (customer_name, contact_no, building_no, street, area, pincode, lat, lon, id_proof_type, id_no, is_bulk, panchayat_name)
    CUSTOMERS = [
        ("Murugan Pillai",   "9876543210", "12A", "Gandhi Street",   "Erode Town", "638001", "11.341", "77.717", "AADHAAR",  "1234 5678 9012", False, "Anthiyur Panchayat"),
        ("Selvi Durai",      "9876543211", "45B", "Anna Nagar",      "Salem",      "636007", "11.667", "78.146", "VOTER_ID", "TN123456789", False, "Bhavani Panchayat"),
        ("Karthikeyan R",    "9876543212", "78C", "Nehru Road",      "Coimbatore", "641001", "11.017", "76.955", "PAN_CARD", "ABCDE1234F", True, "Gobichettipalayam Panchayat"),
        ("Vasantha Kumari",  "9876543213", "21D", "Raja Street",     "Chennai",    "600001", "13.082", "80.270", "AADHAAR",  "9876 5432 1098", True, "Kavundampalayam Panchayat"),
        ("Periasamy S",      "9876543214", "63E", "Meenakshi Nagar", "Madurai",    "625001", "9.9252", "78.119", "VOTER_ID", "TN987654321", False, "Modakkurichi Panchayat"),
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
