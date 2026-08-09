import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import get_settings

settings = get_settings()
_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int, role: str, exam_id: int | None = None) -> str:
    """Issue a session token.

    A candidate token carries the assessment it was issued for. That claim is
    what stops a code for one paper being reused to open another: authorisation
    is bound to the token, not re-derived from whatever id the client sends.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    if exam_id is not None:
        payload["exam"] = exam_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def generate_access_code() -> str:
    """A human-transcribable one-time code, e.g. K7QP-3M9X.

    Ambiguous glyphs (0/O, 1/I/L) are excluded because these get read off a
    printed sheet and typed under time pressure, where a misread character costs
    an invigilator's attention.
    """
    import secrets

    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    block = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{block()}-{block()}"


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
