
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from config import settings
from database import SessionLocal
from models import AdminUser, PendingAccountVerification
from services.email_service import (
    EmailServiceError,
    send_account_verification_email,
)
from services.email_verification import (
    VERIFICATION_CODE_MAX_ATTEMPTS,
    VERIFICATION_CODE_TTL_MINUTES,
    generate_verification_code,
    hash_verification_code,
    verification_code_expired,
    verification_code_matches,
)
from services.security import hash_password


def create_initial_admin() -> None:
    email = (settings.bootstrap_admin_email or "").strip().lower()
    username = (settings.bootstrap_admin_username or "").strip()
    password = settings.bootstrap_admin_password or ""

    if not email or not username or not password:
        print(
            "ERROR: Configure BOOTSTRAP_ADMIN_EMAIL, "
            "BOOTSTRAP_ADMIN_USERNAME, and "
            "BOOTSTRAP_ADMIN_PASSWORD in your .env file."
        )
        sys.exit(1)

    if len(password) < 12:
        print("ERROR: The bootstrap password must be at least 12 characters.")
        sys.exit(1)

    if len(password) > 128:
        print("ERROR: The bootstrap password must not exceed 128 characters.")
        sys.exit(1)

    with SessionLocal() as db:
        admin_count = db.scalar(
            select(func.count()).select_from(AdminUser)
        )

        if admin_count and admin_count > 0:
            print(
                "An administrator already exists. "
                "Bootstrap stopped; no account was created."
            )
            return

        existing_admin = db.scalar(
            select(AdminUser).where(
                (AdminUser.email == email)
                | (AdminUser.username == username)
            )
        )
        if existing_admin is not None:
            print(
                "ERROR: The administrator email or username already exists."
            )
            sys.exit(1)

        code = generate_verification_code()
        verification = db.scalar(
            select(PendingAccountVerification)
            .where(
                PendingAccountVerification.account_type == "admin",
                PendingAccountVerification.email == email,
            )
            .with_for_update()
        )

        if verification is None:
            verification = PendingAccountVerification(
                account_type="admin",
                email=email,
            )
            db.add(verification)

        verification.name = None
        verification.username = username
        verification.password_hash = hash_password(password)
        verification.code_hash = hash_verification_code("admin", code)
        verification.expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=VERIFICATION_CODE_TTL_MINUTES
        )
        verification.attempts = 0

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(
                "ERROR: Could not start administrator verification. "
                "Check the database before retrying."
            )
            sys.exit(1)

        try:
            send_account_verification_email(
                recipient=email,
                code=code,
                account_type="admin",
                expires_minutes=VERIFICATION_CODE_TTL_MINUTES,
            )
        except EmailServiceError as exc:
            db.delete(verification)
            db.commit()
            print(f"ERROR: {exc}")
            sys.exit(1)

        print(f"A verification code was sent to {email}.")
        print(
            f"The code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes."
        )

        for attempt in range(VERIFICATION_CODE_MAX_ATTEMPTS):
            entered_code = input("Enter the six-digit verification code: ").strip()

            if verification_code_expired(verification.expires_at):
                db.delete(verification)
                db.commit()
                print("ERROR: The verification code expired. Run the script again.")
                sys.exit(1)

            if verification_code_matches(
                "admin",
                entered_code,
                verification.code_hash,
            ):
                admin = AdminUser(
                    username=verification.username or "",
                    email=verification.email,
                    password_hash=verification.password_hash,
                    is_active=True,
                )
                db.add(admin)
                db.delete(verification)

                try:
                    db.commit()
                    print("Initial administrator created successfully.")
                    print(f"Username: {admin.username}")
                    print(f"Email: {admin.email}")
                    print("Password: configured securely; not displayed.")
                except IntegrityError:
                    db.rollback()
                    print(
                        "ERROR: The username or email already exists. "
                        "Check the database before retrying."
                    )
                    sys.exit(1)
                return

            verification.attempts = attempt + 1
            if verification.attempts >= VERIFICATION_CODE_MAX_ATTEMPTS:
                db.delete(verification)
                db.commit()
                print("ERROR: Too many incorrect codes. Run the script again.")
                sys.exit(1)

            db.commit()
            print("That code is incorrect. Try again.")

if __name__ == "__main__":
    create_initial_admin()
