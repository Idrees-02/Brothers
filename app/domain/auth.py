"""Password hashing. PBKDF2-HMAC-SHA256 via stdlib hashlib - no compiled
extension (like bcrypt) so it packages cleanly with PyInstaller."""

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 260_000


def hash_password(plain: str, iterations: int = _ITERATIONS) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        algo, iterations_s, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    if algo != _ALGO:
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations_s)
    )
    return hmac.compare_digest(dk.hex(), hash_hex)
