"""Historical migration helpers; no runtime models are defined here."""

from app.utils.comfun import generate_unique_id


def generate_recognized_unique_id():
    return f"REC-{generate_unique_id()}"


def generate_employee_unique_id():
    return f"EMP-{generate_unique_id()}"
