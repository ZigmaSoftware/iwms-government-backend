from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


def _node_for(source_type, source_obj):
    """Resolve the hierarchy node mirrored from a legacy geo master."""
    if not source_obj:
        return None
    return HierarchyNode.objects.filter(
        is_deleted=False,
        custom_properties__source_type=source_type,
        custom_properties__source_id=source_obj.unique_id,
    ).first()


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

        # Fallback node so the seeder still works if a panchayat wasn't mirrored.
        fallback_node = HierarchyNode.objects.filter(
            is_deleted=False, custom_properties__source_type="district",
        ).first()

        count = 0
        for idx, (
            cust_name, contact, building_no, street, area,
            pincode, lat, lon, id_proof_type, id_no, is_bulk, panchayat_name
        ) in enumerate(self.CUSTOMERS):
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name,
                is_deleted=False,
            ).select_related("district_id").first()

            # Geography is now a single hierarchy node (deepest available).
            location_node = (
                _node_for("panchayat", panchayat)
                or _node_for("district", getattr(panchayat, "district_id", None))
                or fallback_node
            )
            if not location_node:
                self.log(f"No hierarchy node for {cust_name} — run geo_to_hierarchy seeder first. Skipping.")
                continue

            _, created = CustomerCreation.objects.update_or_create(
                id_no=id_no,
                defaults={
                    "customer_name": cust_name,
                    "contact_no": contact,
                    "building_no": building_no,
                    "street": street,
                    "area": area,
                    "location_node": location_node,
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
