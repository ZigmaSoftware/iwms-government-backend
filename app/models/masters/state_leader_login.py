from app.utils.comfun import generate_unique_id


def generate_state_leader_id():
    return f"SLDR-{generate_unique_id()}"
