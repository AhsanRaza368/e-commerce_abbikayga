
import logging

import jwt
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from models import Customer, Listing

from schemas import (
    CustomerLogin,
    CustomerProfileUpdate,
    CustomerPublic,
    CustomerSignupResend,
    CustomerSignup,
    CustomerSignupVerification,
    ListingPublic,
    CustomerPasswordResetConfirm,
    CustomerPasswordResetRequest,
)
from database import get_db
from services.customer_security import (
    create_customer_access_token,
    decode_customer_access_token,
)
from services.uploads import (
    PROFILE_IMAGE_URL_PREFIX,
    normalize_customer_profile_picture,
    resolve_profile_image_path,
)
from services.rate_limiter import limiter
from services.security import hash_password, verify_password
import hashlib
import os
import secrets

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from models import CustomerPasswordResetToken, PendingAccountVerification


from services.email_service import (
    EmailServiceError,
    send_account_verification_email,
    send_password_reset_email,
)
from services.email_verification import (
    VERIFICATION_CODE_MAX_ATTEMPTS,
    VERIFICATION_CODE_TTL_MINUTES,
    generate_verification_code,
    hash_verification_code,
    verification_code_expired,
    verification_code_matches,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/customers",
    tags=["Customer Authentication"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    """Return the active customer authenticated by a valid customer JWT."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired customer authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_customer_access_token(credentials.credentials)
        customer_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized

    customer = db.get(Customer, customer_id)

    if customer is None or not customer.is_active:
        raise unauthorized

    return customer


@router.post("/signup", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/hour")
def request_customer_signup_verification(
    request: Request,
    response: Response,
    payload: CustomerSignup,
    db: Session = Depends(get_db),
):
    """Email a code required to complete customer registration."""

    email = str(payload.email).strip().lower()
    name = payload.name.strip()

    if len(name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name must contain at least 2 non-space characters.",
        )

    existing_customer = db.scalar(
        select(Customer).where(Customer.email == email)
    )

    if existing_customer is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    code = generate_verification_code()
    verification = db.scalar(
        select(PendingAccountVerification)
        .where(
            PendingAccountVerification.account_type == "customer",
            PendingAccountVerification.email == email,
        )
        .with_for_update()
    )

    if verification is None:
        verification = PendingAccountVerification(
            account_type="customer",
            email=email,
        )
        db.add(verification)

    verification.name = name
    verification.username = None
    verification.password_hash = hash_password(payload.password)
    verification.code_hash = hash_verification_code("customer", code)
    verification.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )
    verification.attempts = 0

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    try:
        send_account_verification_email(
            recipient=email,
            code=code,
            account_type="customer",
            expires_minutes=VERIFICATION_CODE_TTL_MINUTES,
        )
    except EmailServiceError as exc:
        db.delete(verification)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the verification code. Please try again later.",
        ) from exc

    return {
        "message": (
            "A six-digit verification code was sent to your email address. "
            f"It expires in {VERIFICATION_CODE_TTL_MINUTES} minutes."
        )
    }


@router.post("/signup/resend-code", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/hour")
def resend_customer_signup_verification(
    request: Request,
    response: Response,
    payload: CustomerSignupResend,
    db: Session = Depends(get_db),
):
    """Send a replacement code for a pending customer registration."""

    email = str(payload.email).strip().lower()
    verification = db.scalar(
        select(PendingAccountVerification)
        .where(
            PendingAccountVerification.account_type == "customer",
            PendingAccountVerification.email == email,
        )
        .with_for_update()
    )

    if verification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending signup was found for this email. Start signup again.",
        )

    code = generate_verification_code()
    verification.code_hash = hash_verification_code("customer", code)
    verification.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )
    verification.attempts = 0
    db.commit()

    try:
        send_account_verification_email(
            recipient=email,
            code=code,
            account_type="customer",
            expires_minutes=VERIFICATION_CODE_TTL_MINUTES,
        )
    except EmailServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the verification code. Please try again later.",
        ) from exc

    return {
        "message": (
            "A new verification code was sent. Any earlier code is no longer "
            "valid."
        )
    }


@router.post(
    "/signup/verify",
    response_model=CustomerPublic,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/hour")
def verify_customer_signup(
    request: Request,
    response: Response,
    payload: CustomerSignupVerification,
    db: Session = Depends(get_db),
):
    """Create a customer account after its email code is verified."""

    email = str(payload.email).strip().lower()
    verification = db.scalar(
        select(PendingAccountVerification)
        .where(
            PendingAccountVerification.account_type == "customer",
            PendingAccountVerification.email == email,
        )
        .with_for_update()
    )

    if verification is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired. Request a new code.",
        )

    if verification_code_expired(verification.expires_at):
        db.delete(verification)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired. Request a new code.",
        )

    if not verification_code_matches(
        "customer",
        payload.code,
        verification.code_hash,
    ):
        verification.attempts += 1
        if verification.attempts >= VERIFICATION_CODE_MAX_ATTEMPTS:
            db.delete(verification)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many incorrect codes. Request a new verification code.",
            )

        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is incorrect.",
        )

    existing_customer = db.scalar(
        select(Customer).where(Customer.email == email)
    )
    if existing_customer is not None:
        db.delete(verification)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    customer = Customer(
        name=verification.name or "",
        email=email,
        password_hash=verification.password_hash,
        is_active=True,
    )
    db.add(customer)
    db.delete(verification)

    try:
        db.commit()
        db.refresh(customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return customer


@router.post("/login")
@limiter.limit("5/minute")
def customer_login(
    request: Request,
    response: Response,
    payload: CustomerLogin,
    db: Session = Depends(get_db),
):
    """Authenticate a customer and issue a customer-only JWT."""

    email = str(payload.email).strip().lower()

    customer = db.scalar(
        select(Customer).where(Customer.email == email)
    )

    if (
        customer is None
        or not customer.is_active
        or not verify_password(payload.password, customer.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_customer_access_token(customer.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "customer": CustomerPublic.model_validate(customer),
    }


@router.get("/me", response_model=CustomerPublic)
def get_customer_profile(
    current_customer: Customer = Depends(get_current_customer),
):
    """Return the profile of the authenticated customer."""

    return current_customer


@router.patch("/me", response_model=CustomerPublic)
def update_customer_profile(
    payload: CustomerProfileUpdate,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Update the profile of the authenticated customer."""

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update.",
        )

    # Validate and normalize the name.
    if "name" in updates:
        if updates["name"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name cannot be empty.",
            )

        name = updates["name"].strip()

        if len(name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name must contain at least 2 non-space characters.",
            )

        updates["name"] = name

    # Normalize email and prevent duplicate customer email addresses.
    if "email" in updates:
        if updates["email"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email cannot be empty.",
            )

        email = str(updates["email"]).strip().lower()

        existing_customer = db.scalar(
            select(Customer).where(
                Customer.email == email,
                Customer.id != current_customer.id,
            )
        )

        if existing_customer is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        updates["email"] = email

    # A blank phone number clears the optional phone field.
    if "phone" in updates and updates["phone"] is not None:
        phone = updates["phone"].strip()
        updates["phone"] = phone or None

    for field, value in updates.items():
        setattr(current_customer, field, value)

    try:
        db.commit()
        db.refresh(current_customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The email address is already in use.",
        )

    return current_customer


@router.put("/me/profile-picture", response_model=CustomerPublic)
@limiter.limit("10/hour")
async def update_customer_profile_picture(
    request: Request,
    response: Response,
    picture: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Replace the authenticated customer's profile picture."""

    previous_url = current_customer.profile_picture_url
    current_customer.profile_picture_data = (
        await normalize_customer_profile_picture(picture)
    )
    current_customer.profile_picture_url = (
        "/customers/me/profile-picture"
    )

    try:
        db.commit()
        db.refresh(current_customer)
    except SQLAlchemyError:
        db.rollback()
        raise

    if (
        previous_url is not None
        and previous_url.startswith(PROFILE_IMAGE_URL_PREFIX)
    ):
        previous_path = resolve_profile_image_path(previous_url)
        if previous_path is not None:
            try:
                previous_path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove a replaced profile image.")

    return current_customer


@router.get("/me/profile-picture", include_in_schema=False)
def get_customer_profile_picture(
    current_customer: Customer = Depends(get_current_customer),
):
    """Serve the authenticated customer's profile picture."""

    if current_customer.profile_picture_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile picture has been uploaded.",
        )

    if current_customer.profile_picture_data is not None:
        return Response(
            content=current_customer.profile_picture_data,
            media_type="image/webp",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    picture_path = resolve_profile_image_path(
        current_customer.profile_picture_url
    )

    if picture_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile picture not found.",
        )

    return FileResponse(
        path=picture_path,
        media_type="image/webp",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


CUSTOMER_RESET_TOKEN_MINUTES = 30

CUSTOMER_RESET_MESSAGE = (
    "If an active customer account matches that email, "
    "password-reset instructions will be sent."
)


@router.post("/reset_password")
@limiter.limit("3/hour")
def request_customer_password_reset(
    request: Request,
    response: Response,
    payload: CustomerPasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Send a password-reset email without exposing account existence."""

    email = str(payload.email).strip().lower()

    customer = db.scalar(
        select(Customer).where(Customer.email == email)
    )

    # Use the same public response for nonexistent and inactive accounts.
    if customer is None or not customer.is_active:
        return {"message": CUSTOMER_RESET_MESSAGE}

    now = datetime.now(timezone.utc)

    # Invalidate previous unused reset links.
    previous_tokens = db.scalars(
        select(CustomerPasswordResetToken).where(
            CustomerPasswordResetToken.customer_id == customer.id,
            CustomerPasswordResetToken.used_at.is_(None),
        )
    ).all()

    for record in previous_tokens:
        record.used_at = now

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    reset_record = CustomerPasswordResetToken(
        customer_id=customer.id,
        token_hash=token_hash,
        expires_at=now + timedelta(
            minutes=CUSTOMER_RESET_TOKEN_MINUTES
        ),
    )

    db.add(reset_record)
    db.commit()

    base_url = os.getenv(
        "APP_BASE_URL",
        "http://127.0.0.1:8000",
    ).strip().rstrip("/")

    reset_url = (
        f"{base_url}/customer/reset-password?"
        f"{urlencode({'token': raw_token})}"
    )

    try:
        send_password_reset_email(
            recipient=customer.email,
            reset_url=reset_url,
            expires_minutes=CUSTOMER_RESET_TOKEN_MINUTES,
        )
    except EmailServiceError:
        # Don't leave a usable reset token if delivery failed.
        reset_record.used_at = datetime.now(timezone.utc)
        db.commit()

        logger.exception("Customer password-reset email delivery failed")

    return {"message": CUSTOMER_RESET_MESSAGE}


@router.post("/reset_password/confirm")
@limiter.limit("5/minute")
def confirm_customer_password_reset(
    request: Request,
    response: Response,
    payload: CustomerPasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Change a customer's password with a valid, one-time reset token."""

    token_hash = hashlib.sha256(
        payload.token.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc)

    # Lock the token while checking and consuming it.
    reset_record = db.scalar(
        select(CustomerPasswordResetToken)
        .where(CustomerPasswordResetToken.token_hash == token_hash)
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

    customer = db.get(Customer, reset_record.customer_id)

    if customer is None or not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password-reset link is invalid or expired.",
        )

    try:
        customer.password_hash = hash_password(payload.new_password)
        reset_record.used_at = now

        # Invalidate every other unused reset link for this customer.
        other_tokens = db.scalars(
            select(CustomerPasswordResetToken)
            .where(
                CustomerPasswordResetToken.customer_id == customer.id,
                CustomerPasswordResetToken.id != reset_record.id,
                CustomerPasswordResetToken.used_at.is_(None),
            )
            .with_for_update()
        ).all()

        for record in other_tokens:
            record.used_at = now

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


@router.get("/me/listings", response_model=list[ListingPublic])
def get_my_listings(
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Return advertisements created by the authenticated customer."""

    statement = (
        select(Listing)
        .options(
            selectinload(Listing.images),
            selectinload(Listing.category),
        )
        .where(Listing.customer_id == current_customer.id)
        .order_by(Listing.created_at.desc(), Listing.id.desc())
    )

    return db.scalars(statement).all()


@router.delete("/me/listings/{listing_id}")
def delete_my_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Remove an advertisement owned by the authenticated customer."""

    statement = (
        select(Listing)
        .where(
            Listing.id == listing_id,
            Listing.customer_id == current_customer.id,
        )
        .with_for_update()
    )

    listing = db.scalar(statement)

    # Do not reveal whether another customer's listing exists.
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found.",
        )

    if listing.status == "removed":
        return {"message": "Advertisement has already been removed."}

    listing.status = "removed"
    listing.rejection_reason = None
    listing.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Advertisement removed successfully."}
