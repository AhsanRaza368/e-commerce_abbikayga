
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from config import settings


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password using the recommended Argon2 configuration."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against its stored hash."""
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(admin_id: int) -> str:
    """Create a short-lived JWT for an administrator."""
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(admin_id),
        "role": "admin",
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }

    return jwt.encode(
        payload,
        settings.admin_secret_key,
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Validate a JWT and return its claims."""
    payload = jwt.decode(
        token,
        settings.admin_secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["sub", "exp", "iat"]},
    )

    if payload.get("role") != "admin":
        raise jwt.InvalidTokenError("Invalid administrator role.")

    return payload
