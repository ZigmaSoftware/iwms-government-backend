# api/models/login_audit.py
from app.utils.comfun import generate_unique_id


def generate_login_id():
    return f"LOGINAUDIT-{generate_unique_id()}"
