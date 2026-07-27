from decimal import Decimal

from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.geo import spread_points
from app.management.commands.seeders.tn_geo_data import DISTRICTS, STREET_NAMES, TAMIL_NAME_POOL
from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.ward_utils import geo_defaults_for_local_body, wards_for_district
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.wastetype import WasteType

# Distinct 6-digit pincode ranges per local body type within a district's
# 3-digit prefix (e.g. Erode "638") — plausible without inventing per-ward
# real postal data.
_PINCODE_BODY_OFFSET = {
    "corporation": 0,
    "municipality": 10,
    "town_panchayat": 20,
    "panchayat_union": 30,
}

# min 6 chars, 1 uppercase + 1 lowercase + 1 digit — same convention as CustomerUserSeeder
DEFAULT_CUSTOMER_PASSWORD = "Customer1"

ID_PROOF_CYCLE = ["AADHAAR", "VOTER_ID", "PAN_CARD"]
# Matches the household-collection waste-type restriction (see TripPlanSeeder) —
# household routes only ever handle these 4 segregated streams.
CUSTOMER_WASTE_TYPES = ["Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste"]

# 2 Individual-House customers per seeded Ward, across every local body
# type (Corporation, Municipality, Town Panchayat, Panchayat Union, each
# Panchayat) — every customer sits inside a real ward, placed with a
# deterministic jitter around that ward's own centroid so household routes
# never show a customer outside their own ward. Everything here is
# Individual House only — the only customer type this project seeds — per
# the "Individual house" requirement.
CUSTOMERS_PER_WARD = 2


class CustomerCreationSeeder(BaseSeeder):
    name = "CustomerCreationSeeder"

    def run(self):
        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property = SubProperty.objects.filter(
            property_id=property_obj, sub_property_name="Individual House", is_deleted=False
        ).first() if property_obj else None
        if not property_obj or not sub_property:
            self.log("Property/SubProperty not found — run PropertySeeder first.")
            return

        waste_types = list(
            WasteType.objects.filter(waste_type_name__in=CUSTOMER_WASTE_TYPES, is_deleted=False)
        )

        count = 0
        global_idx = 0
        for district_name, geo in DISTRICTS.items():
            locations = self._build_locations(district_name, geo)
            if not locations:
                self.log(f"No wards/panchayats resolved for '{district_name}' — skipping customers.")
                continue

            for location in locations:
                points = spread_points(location["lat"], location["lon"], CUSTOMERS_PER_WARD, radius_km=0.4)
                for slot, (lat, lon) in enumerate(points):
                    created = self._seed_customer(
                        global_idx, location, lat, lon,
                        property_obj, sub_property, waste_types,
                    )
                    if created:
                        count += 1
                    global_idx += 1

        self.log(f"---Customers seeded ({count} created)---")

    def _build_locations(self, district_name, geo):
        """One placement target per seeded Ward, across every local body
        type (Corporation, Municipality, Town Panchayat, Panchayat Union,
        each Panchayat) — every customer now sits inside a real ward, not
        just a bare local body. Each carries its own lat/lon (the ward's
        own centroid), pincode, and the full flat-geo FK block plus the
        ward itself."""
        locations = []
        prefix3 = geo["corporation_pincode_base"][:3]
        panchayat_pincodes = {name: pincode for name, _lat, _lon, pincode in geo["panchayats"]}
        body_ward_counters = {}

        for ward_info in wards_for_district(district_name):
            ward, parent_type, parent = ward_info["ward"], ward_info["parent_type"], ward_info["parent"]
            point = (ward.coordinates or [None])[0]
            if not point:
                continue
            lat, lon = point["latitude"], point["longitude"]

            if parent_type == "panchayat":
                pincode = panchayat_pincodes.get(parent.panchayat_name, f"{prefix3}000")
            else:
                body_ward_counters[parent_type] = body_ward_counters.get(parent_type, 0) + 1
                pincode = f"{prefix3}{_PINCODE_BODY_OFFSET[parent_type] + body_ward_counters[parent_type]:03d}"

            geo_defaults = geo_defaults_for_local_body(parent_type, parent)
            locations.append({
                "area": ward.ward_name,
                "lat": lat,
                "lon": lon,
                "pincode": pincode,
                "ward": ward,
                **{field: value for field, value in geo_defaults.items()},
            })

        return locations

    def _seed_customer(self, idx, location, lat, lon, property_obj, sub_property, waste_types):
        name = TAMIL_NAME_POOL[idx % len(TAMIL_NAME_POOL)]
        street = STREET_NAMES[idx % len(STREET_NAMES)]
        building_no = f"{(idx % 99) + 1}{'ABCDE'[idx % 5]}"
        contact_no = str(9000000001 + idx)
        id_proof_type = ID_PROOF_CYCLE[idx % len(ID_PROOF_CYCLE)]
        id_no = self._id_no(id_proof_type, idx)
        member_count = 2 + (idx % 5)
        sqft = Decimal(800 + (idx % 12) * 150)
        water_lpd = Decimal(120 + (idx % 8) * 20)
        waste_kg_per_day = Decimal(str(round(1.5 + (idx % 5) * 0.5, 2)))
        slug = name.lower().replace(" ", ".")
        email = f"{slug}.{idx:03d}@example.com"

        family_members = [
            {
                "member_name": TAMIL_NAME_POOL[(idx + m) % len(TAMIL_NAME_POOL)],
                "id_proof_type": "AADHAAR",
                "id_no": f"FAM-{idx}-{m}",
            }
            for m in range(member_count)
        ]

        defaults = {
            "customer_name": name,
            "contact_no": contact_no,
            "username": contact_no,
            "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
            "email": email,
            "building_no": building_no,
            "street": street,
            "area": location["area"],
            "state": location["state"],
            "district": location["district"],
            "area_type": location["area_type"],
            "corporation": location["corporation"],
            "municipality": location["municipality"],
            "town_panchayat": location["town_panchayat"],
            "panchayat_union": location["panchayat_union"],
            "panchayat": location["panchayat"],
            "ward": location["ward"],
            "pincode": location["pincode"],
            "latitude": f"{lat:.6f}",
            "longitude": f"{lon:.6f}",
            "id_proof_type": id_proof_type,
            "sqft": sqft,
            "water_consumption_lpd": water_lpd,
            "waste_collection_kg_per_day": waste_kg_per_day,
            "member_count": member_count,
            "family_members": family_members,
            "property_ref": property_obj,
            "sub_property": sub_property,
            "is_bulkwaste_generator": False,
            # Clear apartment/industry fields — this seeder only ever
            # produces Individual House customers.
            "apartment_name": None,
            "block_no": None,
            "flat_no": None,
            "apartment_unique_id": None,
            "villa_no": None,
            "industry_name": None,
            "industry_type": None,
            "is_active": True,
            "is_deleted": False,
        }

        customer, created = CustomerCreation.objects.update_or_create(
            id_no=id_no,
            defaults=defaults,
        )
        if waste_types:
            customer.waste_types.set(waste_types)
        return created

    @staticmethod
    def _id_no(id_proof_type, idx):
        if id_proof_type == "AADHAAR":
            return f"{4000 + idx:04d} {5000 + idx:04d} {6000 + idx:04d}"
        if id_proof_type == "VOTER_ID":
            return f"TN{100000000 + idx:09d}"
        # PAN-shaped (5 letters + 4 digits + 1 letter), unique per customer.
        letters = "".join(chr(65 + ((idx + k * 3) % 26)) for k in range(5))
        return f"{letters}{1000 + idx:04d}{chr(65 + (idx % 26))}"
