import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from config import settings


VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_CODE_MAX_ATTEMPTS = 5


def generate_verification_code() -> str:
    """Return a cryptographically random six-digit verification code."""

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(account_type: str, code: str) -> str:
    """Return an HMAC of a verification code using the account secret."""

    secret = (
        settings.customer_secret_key
        if account_type == "customer"
        else settings.admin_secret_key
    )
    return hmac.new(
        secret.encode("utf-8"),
        f"{account_type}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verification_code_matches(
    account_type: str,
    code: str,
    expected_hash: str,
) -> bool:
    return hmac.compare_digest(
        hash_verification_code(account_type, code),
        expected_hash,
    )


def verification_code_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)
