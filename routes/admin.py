
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import AdminUser, AuditLog, Listing, Report
from routes.auth import get_current_admin
from schemas import ListingModeration, ListingPublic
from services.uploads import resolve_image_path


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/listings",
    tags=["Admin Listing Moderation"],
)


@router.get("/pending", response_model=list[ListingPublic])
def get_pending_listings(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Return pending listings for administrator review."""

    statement = (
        select(Listing)
        .options(
            selectinload(Listing.images),
            selectinload(Listing.category),
        )
        .where(Listing.status == "pending")
        .order_by(Listing.created_at.asc(), Listing.id.asc())
    )

    return db.scalars(statement).all()


@router.patch(
    "/{listing_id}/moderation",
    response_model=ListingPublic,
)
def moderate_listing(
    listing_id: int,
    moderation_data: ListingModeration,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Approve, reject, or remove a listing."""

    listing = db.get(Listing, listing_id)

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )

    new_status = moderation_data.status
    rejection_reason = (
        moderation_data.rejection_reason.strip()
        if moderation_data.rejection_reason
        else None
    )

    if new_status == "rejected" and not rejection_reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A rejection reason is required.",
        )

    old_status = listing.status

    listing.status = new_status
    listing.rejection_reason = (
        rejection_reason if new_status == "rejected" else None
    )
    listing.updated_at = datetime.now(timezone.utc)

    if new_status == "approved":
        listing.approved_at = datetime.now(timezone.utc)

    audit_entry = AuditLog(
        admin_id=current_admin.id,
        action=f"listing_{new_status}",
        entity_type="listing",
        entity_id=listing.id,
        details={
            "previous_status": old_status,
            "new_status": new_status,
            "rejection_reason": rejection_reason,
        },
    )

    try:
        db.add(audit_entry)
        db.commit()
        db.refresh(listing)
    except Exception:
        db.rollback()
        raise

    return listing


@router.delete("/{listing_id}")
def delete_reported_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Permanently delete a listing, its reports, and its image files."""

    listing = db.scalar(
        select(Listing)
        .options(selectinload(Listing.images))
        .where(Listing.id == listing_id)
        .with_for_update()
    )

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )

    image_paths = [
        path
        for image in listing.images
        if (path := resolve_image_path(image.image_url)) is not None
    ]
    report_count = db.scalar(
        select(func.count())
        .select_from(Report)
        .where(Report.listing_id == listing.id)
    )

    audit_entry = AuditLog(
        admin_id=current_admin.id,
        action="listing_deleted",
        entity_type="listing",
        entity_id=listing.id,
        details={
            "title": listing.title,
            "status": listing.status,
            "reports_deleted": report_count,
        },
    )

    try:
        db.execute(delete(Report).where(Report.listing_id == listing.id))
        db.add(audit_entry)
        db.delete(listing)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    for image_path in image_paths:
        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "Could not remove image file for deleted listing %s.",
                listing_id,
            )

    return {"message": "Advertisement and its reports deleted successfully."}
