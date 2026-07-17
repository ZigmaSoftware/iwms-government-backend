from app.utils.comfun import generate_unique_id


def generate_panchayat_leader_id():
    return f"PLDR-{generate_unique_id()}"
