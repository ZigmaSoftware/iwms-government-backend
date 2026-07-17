from app.utils.comfun import generate_unique_id


def generate_login_id():
    return f"AUDITLOG-{generate_unique_id()}"
