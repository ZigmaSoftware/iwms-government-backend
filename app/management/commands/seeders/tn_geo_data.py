"""
Central, real-world Tamil Nadu geographic + naming data for the three
fully-built-out operational districts: Erode, Coimbatore, and Salem.

Coordinates are approximate real-world locality centroids (the same
precision level the rest of the seeders already use), not surveyed data —
sufficient to make dashboards look like they cover real places instead of
one fixed point per district. Every value here is a plain literal (no
randomness), so seeding stays byte-for-byte idempotent across repeated runs.

Note: "Kavundampalayam" is a real Coimbatore locality (near Thudiyalur/
Saravanampatti), not an Erode one — it lives under Coimbatore's corporation
wards below. Erode's rural panchayat list uses "Kodumudi" (a real town on
the Cauvery in Erode district) instead.
"""

DISTRICTS = {
    "Erode": {
        "code": "ERD",
        "vehicle_prefix": "TN33",
        "breakdown_roads": [
            "NH-544",
            "Erode-Kodumudi Road",
            "Perundurai Road",
            "Erode Bypass",
        ],
        "corporation_name": "Erode Corporation",
        "corporation_pincode_base": "63800",
        # (ward_name, latitude, longitude)
        "corporation_wards": [
            ("Erode Fort", 11.3441, 77.7180),
            ("Agraharam", 11.3465, 77.7215),
            ("Surampatti", 11.3395, 77.7100),
            ("Veerappanchatram", 11.3520, 77.7295),
            ("Sampath Nagar", 11.3355, 77.7230),
            ("Diwan Bahadur Road", 11.3410, 77.7150),
            ("Thindal", 11.3610, 77.7280),
            ("Karungalpalayam", 11.3330, 77.7080),
        ],
        # (panchayat_name, latitude, longitude, pincode)
        "panchayats": [
            ("Anthiyur Panchayat", 11.5750, 77.5900, "638501"),
            ("Bhavani Panchayat", 11.4437, 77.6845, "638301"),
            ("Gobichettipalayam Panchayat", 11.4524, 77.4355, "638452"),
            ("Kodumudi Panchayat", 11.0790, 77.8850, "638151"),
            ("Modakkurichi Panchayat", 11.3805, 77.7032, "638104"),
        ],
    },
    "Coimbatore": {
        "code": "CBE",
        "vehicle_prefix": "TN38",
        "breakdown_roads": [
            "NH-948",
            "Avinashi Road",
            "Trichy Road",
            "Mettupalayam Road",
        ],
        "corporation_name": "Coimbatore Corporation",
        "corporation_pincode_base": "64100",
        "corporation_wards": [
            ("RS Puram", 11.0055, 76.9528),
            ("Gandhipuram", 11.0170, 76.9674),
            ("Peelamedu", 11.0290, 77.0040),
            ("Ramanathapuram", 10.9960, 76.9730),
            ("Saibaba Colony", 11.0210, 76.9440),
            ("Singanallur", 11.0010, 77.0290),
            ("Kavundampalayam", 11.0450, 76.9370),
            ("Ganapathy", 11.0330, 76.9520),
        ],
        "panchayats": [
            ("Madukkarai Panchayat", 10.9280, 76.9350, "641105"),
            ("Karamadai Panchayat", 11.2350, 76.9440, "641104"),
        ],
    },
    "Salem": {
        "code": "SLM",
        "vehicle_prefix": "TN30",
        "breakdown_roads": [
            "NH-44",
            "Salem-Coimbatore Highway",
            "Salem-Attur Road",
            "Junction Main Road",
        ],
        "corporation_name": "Salem Corporation",
        "corporation_pincode_base": "63600",
        "corporation_wards": [
            ("Fairlands", 11.6730, 78.1460),
            ("Suramangalam", 11.6790, 78.1290),
            ("Ammapet", 11.6540, 78.1670),
            ("Hasthampatti", 11.6580, 78.1650),
            ("Shevapet", 11.6690, 78.1370),
            ("Alagapuram", 11.6480, 78.1540),
            ("Kondalampatti", 11.7000, 78.1200),
            ("Swarnapuri", 11.6860, 78.1560),
        ],
        "panchayats": [
            ("Omalur Panchayat", 11.7400, 78.0450, "636455"),
            ("Kolathur Panchayat", 11.7100, 78.2900, "636305"),
        ],
    },
}

# Deterministic iteration order used everywhere three districts are looped.
DISTRICT_NAMES = list(DISTRICTS.keys())

# Generic street/locality labels reused across every ward/panchayat (mirrors
# how common street names repeat across real TN towns).
STREET_NAMES = [
    "Gandhi Street",
    "Anna Nagar",
    "Nehru Road",
    "Bazaar Street",
    "Kovil Street",
    "Market Road",
    "Perumal Kovil Street",
    "Mill Road",
    "Cauvery Street",
    "New Bus Stand Road",
    "Agraharam Street",
    "Vellode Road",
    "Railway Feeder Road",
    "Main Road",
    "Kamaraj Nagar",
    "VOC Street",
    "Thiruvalluvar Street",
    "Periyar Nagar",
]

# Common Tamil full names, reused deterministically by index across
# customers/staff (no Faker — Faker's available locales don't produce
# authentically Tamil names, and this keeps output byte-identical on re-run).
TAMIL_NAME_POOL = [
    "Murugan Pillai", "Selvi Durai", "Karthikeyan R", "Vasantha Kumari",
    "Periasamy S", "Chinnasamy K", "Lakshmi Ammal", "Rajendran P",
    "Kalaivani S", "Muthusamy V", "Ponnammal R", "Dhandapani M",
    "Shanthi K", "Govindasamy N", "Meenakshi P", "Saravanan T",
    "Kavitha R", "Elumalai S", "Bhuvaneswari K", "Manikandan V",
    "Revathi S", "Palanisamy K", "Vijayalakshmi N", "Senthilkumar P",
    "Amutha R", "Ravindran S", "Kamala Devi", "Suresh Babu",
    "Anitha M", "Ganesan T", "Deepa K", "Nagarajan V",
    "Latha S", "Balasubramaniam R", "Uma Maheswari", "Sundaram P",
    "Jayalakshmi N", "Kandasamy M", "Radhika S", "Arumugam K",
    "Valli R", "Thangaraj P", "Pushpalatha S", "Rajesh Kumar",
    "Saraswathi M", "Velmurugan S", "Indira K", "Natarajan V",
    "Parvathi B", "Sumathi R", "Malar Vizhi", "Karuppasamy N",
    "Devika S", "Rani Muthu", "Tamilarasi K", "Marimuthu P",
]
