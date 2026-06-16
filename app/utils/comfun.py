import time
import random

def generate_unique_id(prefix: str = "", length: int | None = None) -> str:
    """
    Mimics PHP's uniqid() . rand(10000, 99999)
    Example: '652b8df64c6b310345' or with prefix 'EMP652b8df64c6b310345'
    """
    # PHP uniqid() uses current time in microseconds, hex-encoded
    unique_part = hex(int(time.time() * 1000000))[2:]  # strip '0x'
    random_part = str(random.randint(10000, 99999))
    core = f"{unique_part}{random_part}"
    if length is not None:
        if length < 1:
            core = ""
        else:
            core = core[-length:]
    return f"{prefix}{core}"