
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class EmailServiceError(RuntimeError):
    """Raised when email configuration or delivery fails."""


def _get_smtp_settings() -> tuple[str, int, str, str, str]:
    """Load SMTP settings without exposing credentials."""

    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM_EMAIL", "").strip()

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise EmailServiceError("SMTP_PORT must be a valid integer.") from exc

    if not all([host, username, password, sender]):
        raise EmailServiceError(
            "SMTP configuration is incomplete. Check your .env settings."
        )

    if not 1 <= port <= 65535:
        raise EmailServiceError("SMTP_PORT is outside the valid range.")

    return host, port, username, password, sender


def verify_smtp_connection() -> None:
    """Verify SMTP connectivity and authentication without sending email."""

    host, port, username, password, _sender = _get_smtp_settings()
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailServiceError(
            "Gmail SMTP verification failed. Check the Gmail address, "
            "App Password, host, port, and 2-Step Verification."
        ) from exc


def send_password_reset_email(
    recipient: str,
    reset_url: str,
    expires_minutes: int = 30,
) -> None:
    """Send an administrator password-reset link by Gmail SMTP."""

    host, port, username, password, sender = _get_smtp_settings()

    if not recipient or "\r" in recipient or "\n" in recipient:
        raise EmailServiceError("The recipient email address is invalid.")

    if not reset_url.startswith(("http://", "https://")):
        raise EmailServiceError("The password-reset URL is invalid.")

    safe_url = escape(reset_url, quote=True)

    message = EmailMessage()
    message["Subject"] = "Reset your AbbiKayGa administrator password"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        "A password reset was requested for your AbbiKayGa administrator "
        "account.\n\n"
        f"Use this link to choose a new password:\n{reset_url}\n\n"
        f"This link expires in {expires_minutes} minutes and should only "
        "be used once.\n\n"
        "If you did not request this change, you can ignore this email."
    )

    message.add_alternative(
        f"""
        <html>
          <body>
            <h2>Reset your AbbiKayGa password</h2>
            <p>A password reset was requested for your administrator account.</p>
            <p>
              <a href="{safe_url}">Choose a new password</a>
            </p>
            <p>This link expires in {expires_minutes} minutes and should
            only be used once.</p>
            <p>If you did not request this change, ignore this email.</p>
          </body>
        </html>
        """,
        subtype="html",
    )

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailServiceError(
            "Unable to send the password-reset email. "
            "Check Gmail SMTP configuration and connectivity."
        ) from exc


def send_account_verification_email(
    recipient: str,
    code: str,
    account_type: str,
    expires_minutes: int = 10,
) -> None:
    """Send an account-creation verification code."""

    host, port, username, password, sender = _get_smtp_settings()

    if not recipient or "\r" in recipient or "\n" in recipient:
        raise EmailServiceError("The recipient email address is invalid.")

    account_label = "administrator" if account_type == "admin" else "customer"
    message = EmailMessage()
    message["Subject"] = "Verify your AbbiKayGa account"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Your AbbiKayGa {account_label} account verification code is: "
        f"{code}\n\n"
        f"This code expires in {expires_minutes} minutes and can be used "
        "only once. If you did not request this account, you can ignore "
        "this email."
    )
    message.add_alternative(
        "<html><body>"
        f"<h2>Verify your AbbiKayGa {escape(account_label)} account</h2>"
        f"<p>Your verification code is "
        f"<strong>{escape(code)}</strong>.</p>"
        f"<p>This code expires in {expires_minutes} minutes and can be used "
        "only once.</p>"
        "<p>If you did not request this account, ignore this email.</p>"
        "</body></html>",
        subtype="html",
    )

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailServiceError(
            "Unable to send the verification email. "
            "Check SMTP configuration and connectivity."
        ) from exc
