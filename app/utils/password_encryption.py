import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_password(plain_password: str) -> str:
    return _get_fernet().encrypt(plain_password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Returns the original plain-text password.
    Returns empty string if the stored value is an old one-way hash
    (Django pbkdf2/bcrypt) that cannot be decrypted.
    """
    if not encrypted_password:
        return ""
    # Old Django hashes are not Fernet tokens — skip them silently
    if encrypted_password.startswith(("pbkdf2_", "bcrypt$", "argon2")):
        return ""
    try:
        return _get_fernet().decrypt(encrypted_password.encode()).decode()
    except (InvalidToken, Exception):
        return ""
