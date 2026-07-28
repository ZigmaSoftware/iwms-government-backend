from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import spread_points
from app.management.commands.seeders.tn_geo_data import (
    DISTRICTS,
    STREET_NAMES,
    TAMIL_NAME_POOL,
)
from app.management.commands.seeders.ward_utils import (
    geo_defaults_for_local_body,
    wards_for_district,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.wastetype import WasteType

# Distinct 6-digit pincode ranges per local body type within a district's
# 3-digit prefix (e.g. Erode "638") - plausible without inventing per-ward
# real postal data.
_PINCODE_BODY_OFFSET = {
    "corporation": 0,
    "municipality": 10,
    "town_panchayat": 20,
    "panchayat_union": 30,
}

# min 6 chars, 1 uppercase + 1 lowercase + 1 digit - same convention as
# CustomerUserSeeder
DEFAULT_CUSTOMER_PASSWORD = "Customer1"

ID_PROOF_CYCLE = ["AADHAAR", "VOTER_ID", "PAN_CARD"]

# Matches the household-collection waste-type restriction (see TripPlanSeeder) -
# household routes only ever handle these 4 segregated streams.
CUSTOMER_WASTE_TYPES = ["Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste"]

# 2 Individual-House customers per seeded Ward, across every local body type.
CUSTOMERS_PER_WARD = 2


class CustomerCreationSeeder(BaseSeeder):
    name = "CustomerCreationSeeder"

    def run(self):
        property_obj = Property.objects.filter(
            property_name="Residential",
            is_deleted=False,
        ).first()
        sub_property = (
            SubProperty.objects.filter(
                property_id=property_obj,
                sub_property_name="Individual House",
                is_deleted=False,
            ).first()
            if property_obj
            else None
        )
        if not property_obj or not sub_property:
            self.log("Property/SubProperty not found - run PropertySeeder first.")
            return

        waste_types = list(
            WasteType.objects.filter(
                waste_type_name__in=CUSTOMER_WASTE_TYPES,
                is_deleted=False,
            )
        )
        if not waste_types:
            self.log("Waste types missing - run WasteTypeSeeder first.")
            return

        created_count = 0
        updated_count = 0
        global_idx = 0

        for district_name, geo in DISTRICTS.items():
            locations = self._build_locations(district_name, geo)
            if not locations:
                self.log(
                    f"No wards/local bodies resolved for '{district_name}' - skipping customers."
                )
                continue

            for location_idx, location in enumerate(locations, start=1):
                points = spread_points(
                    location["center_lat"],
                    location["center_lon"],
                    CUSTOMERS_PER_WARD,
                    radius_km=0.08,
                )

                for point_idx, (lat, lon) in enumerate(points, start=1):
                    name_seed = TAMIL_NAME_POOL[global_idx % len(TAMIL_NAME_POOL)]
                    cust_name = self._customer_name(name_seed, district_name, global_idx)
                    street = STREET_NAMES[global_idx % len(STREET_NAMES)]
                    building_no = str((location_idx - 1) * CUSTOMERS_PER_WARD + point_idx)
                    area = location["ward"].ward_name
                    contact = self._contact_number(district_name, location_idx, point_idx)
                    id_proof_type = ID_PROOF_CYCLE[global_idx % len(ID_PROOF_CYCLE)]
                    id_no = self._id_number(district_name, location_idx, point_idx)

                    defaults = {
                        "customer_name": cust_name,
                        "contact_no": contact,
                        "username": contact,
                        "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                        "building_no": building_no,
                        "street": street,
                        "area": area,
                        "ward": location["ward"],
                        "pincode": location["pincode"],
                        "latitude": f"{lat:.6f}",
                        "longitude": f"{lon:.6f}",
                        "id_proof_type": id_proof_type,
                        "property_ref": property_obj,
                        "sub_property": sub_property,
                        "is_bulkwaste_generator": False,
                        "apartment_name": None,
                        "block_no": None,
                        "flat_no": None,
                        "apartment_unique_id": None,
                        "villa_no": None,
                        "industry_name": None,
                        "industry_type": None,
                        "is_active": True,
                        "is_deleted": False,
                        "id_no": id_no,
                    }
                    defaults.update(
                        geo_defaults_for_local_body(
                            location["parent_type"],
                            location["parent"],
                        )
                    )

                    customer, created = CustomerCreation.objects.update_or_create(
                        id_no=id_no,
                        defaults=defaults,
                    )
                    customer.waste_types.set(waste_types)

                    if created:
                        created_count += 1
                        self.log(f"Created customer: {cust_name}")
                    else:
                        updated_count += 1
                        self.log(f"Updated customer: {cust_name}")

                    global_idx += 1

        self.log(
            f"---Customers seeded ({created_count} created, {updated_count} updated)---"
        )

    def _build_locations(self, district_name, geo):
        locations = []
        for entry in wards_for_district(district_name):
            ward = entry["ward"]
            parent_type = entry["parent_type"]
            parent = entry["parent"]
            center_lat, center_lon = self._center_for_ward(ward, geo)
            locations.append(
                {
                    "ward": ward,
                    "parent_type": parent_type,
                    "parent": parent,
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "pincode": self._pincode_for_location(
                        district_name,
                        geo,
                        parent_type,
                        parent,
                        len(locations) + 1,
                    ),
                }
            )
        return locations

    def _center_for_ward(self, ward, geo):
        coords = ward.coordinates or []
        if coords:
            first = coords[0]
            try:
                return float(first["latitude"]), float(first["longitude"])
            except (KeyError, TypeError, ValueError):
                pass

        if geo.get("corporation_wards"):
            _name, lat, lon = geo["corporation_wards"][0]
            return float(lat), float(lon)
        if geo.get("panchayats"):
            _name, lat, lon, _pincode = geo["panchayats"][0]
            return float(lat), float(lon)
        return 11.0, 77.0

    def _pincode_for_location(
        self,
        district_name,
        geo,
        parent_type,
        parent,
        location_idx,
    ):
        if parent_type == "panchayat":
            parent_name = getattr(parent, "panchayat_name", "")
            for panchayat_name, _lat, _lon, pincode in geo.get("panchayats", []):
                if panchayat_name == parent_name:
                    return pincode

        if parent_type == "corporation":
            base = int(geo["corporation_pincode_base"])
            return f"{base + location_idx:06d}"

        district_prefix = {
            "Erode": "638",
            "Coimbatore": "641",
            "Salem": "636",
        }.get(district_name, "600")
        suffix = _PINCODE_BODY_OFFSET.get(parent_type, 40) + location_idx
        return f"{district_prefix}{suffix:03d}"

    def _contact_number(self, district_name, location_idx, point_idx):
        district_prefix = {
            "Erode": "810",
            "Coimbatore": "820",
            "Salem": "830",
        }.get(district_name, "840")
        return f"9{district_prefix}{location_idx:03d}{point_idx:02d}"

    def _id_number(self, district_name, location_idx, point_idx):
        district_code = DISTRICTS[district_name]["code"]
        return f"{district_code}-CUST-{location_idx:03d}{point_idx:02d}"

    def _customer_name(self, seed_name, district_name, global_idx):
        district_code = DISTRICTS[district_name]["code"]
        return f"{seed_name} {district_code}-{global_idx + 1:02d}"
