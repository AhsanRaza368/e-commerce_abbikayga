
from datetime import datetime, timedelta, timezone

import jwt

from config import settings


def create_customer_access_token(customer_id: int) -> str:
    """Create a short-lived JWT specifically for a customer."""

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(customer_id),
        "role": "customer",
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }

    return jwt.encode(
        payload,
        settings.customer_secret_key,
        algorithm=settings.algorithm,
    )


def decode_customer_access_token(token: str) -> dict:
    """Validate a customer JWT using the customer-only secret."""

    payload = jwt.decode(
        token,
        settings.customer_secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["sub", "exp", "iat"]},
    )

    if payload.get("role") != "customer":
        raise jwt.InvalidTokenError("Invalid customer role.")

    return payload
