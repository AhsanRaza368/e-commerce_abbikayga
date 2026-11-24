import hashlib
import logging
import os
import secrets

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from models import PasswordResetToken
from schemas import PasswordResetConfirm
from schemas import PasswordResetRequest
from services.email_service import (
    EmailServiceError,
    send_password_reset_email,
)
from sqlalchemy import select
from models import AdminUser
from services.security import hash_password
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from services.rate_limiter import limiter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

import jwt

from database import get_db
from models import AdminUser
from schemas import AdminLogin, AdminPublic
from services.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)
# from dotenv import load_dotenv

# load_dotenv()
# code=os.getenv("admin_code")

router = APIRouter(prefix="/auth", tags=["Admin Authentication"])

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Return the active administrator authenticated by a valid JWT."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        admin_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized

    admin = db.get(AdminUser, admin_id)

    if admin is None or not admin.is_active:
        raise unauthorized

    return admin


@router.post("/login")
@limiter.limit("5/minute")
def admin_login(
    request: Request,
    response: Response,
    login_data: AdminLogin,
    db: Session = Depends(get_db),
):
    """Authenticate an administrator and issue a JWT."""

    email = str(login_data.email).strip().lower()

    admin = db.scalar(
        select(AdminUser).where(AdminUser.email == email)
    )

    if (
        admin is None
        or not admin.is_active
        or not verify_password(login_data.password, admin.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(admin.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": AdminPublic.model_validate(admin),
    }


@router.get("/me", response_model=AdminPublic)
def get_admin_profile(
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Return the authenticated administrator's profile."""

    return current_admin


logger = logging.getLogger(__name__)

RESET_TOKEN_MINUTES = 30

RESET_REQUEST_MESSAGE = (
    "If an active administrator account matches that email, "
    "password-reset instructions will be sent."
)


@router.post("/reset_password")
@limiter.limit("3/hour")
def request_password_reset(
    request: Request,
    response: Response,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Request an administrator password-reset email."""

    email = str(payload.email).strip().lower()

    admin = db.scalar(
        select(AdminUser).where(AdminUser.email == email)
    )

    # Always return the same public response to avoid revealing
    # whether an administrator email address exists.
    if admin is None or not admin.is_active:
        return {"message": RESET_REQUEST_MESSAGE}

    now = datetime.now(timezone.utc)

    # Invalidate earlier, unused reset tokens for this administrator.
    previous_tokens = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.admin_id == admin.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()

    for previous_token in previous_tokens:
        previous_token.used_at = now

    # Only the SHA-256 hash of the random token is stored in the database.
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    reset_record = PasswordResetToken(
        admin_id=admin.id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=RESET_TOKEN_MINUTES),
    )

    db.add(reset_record)
    db.commit()

    # Construct the destination from trusted server configuration,
    # never from an incoming Host header.
    base_url = os.getenv(
        "APP_BASE_URL",
        "http://127.0.0.1:8000",
    ).strip().rstrip("/")

    reset_url = (
        f"{base_url}/admin/reset-password?"
        f"{urlencode({'token': raw_token})}"
    )

    try:
        send_password_reset_email(
            recipient=admin.email,
            reset_url=reset_url,
            expires_minutes=RESET_TOKEN_MINUTES,
        )
    except EmailServiceError:
        # Revoke the token if the email could not be sent.
        reset_record.used_at = datetime.now(timezone.utc)
        db.commit()

        logger.exception("Password-reset email delivery failed")

    return {"message": RESET_REQUEST_MESSAGE}


@router.post("/reset_password/confirm")
@limiter.limit("5/minute")
def confirm_password_reset(
    request: Request,
    response: Response,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Set a new administrator password using a valid one-time token."""

    token_hash = hashlib.sha256(
        payload.token.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc)

    # Lock the token row while it is checked and consumed. This helps
    # prevent two concurrent requests from using the same token.
    reset_record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )

    if (
        reset_record is None
        or reset_record.used_at is not None
        or reset_record.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password-reset link is invalid or expired.",
        )

    admin = db.get(AdminUser, reset_record.admin_id)

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password-reset link is invalid or expired.",
        )

    try:
        admin.password_hash = hash_password(payload.new_password)
        reset_record.used_at = now

        # Invalidate any other outstanding reset links for this admin.
        other_tokens = db.scalars(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.admin_id == admin.id,
                PasswordResetToken.id != reset_record.id,
                PasswordResetToken.used_at.is_(None),
            )
            .with_for_update()
        ).all()

        for other_token in other_tokens:
            other_token.used_at = now

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            "Password reset successful. You can now sign in "
            "with your new password."
        )
    }
