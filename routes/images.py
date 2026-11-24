
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Listing, ListingImage
from services.uploads import resolve_image_path
from models import AdminUser, Listing, ListingImage
from routes.auth import get_current_admin


router = APIRouter(tags=["Listing Images"])


@router.get("/listing-images/{filename}", include_in_schema=False)
def serve_listing_image(
    filename: str,
    db: Session = Depends(get_db),
):
    """Serve an image only if its listing is publicly approved."""

    image_url = f"/listing-images/{filename}"

    statement = (
        select(ListingImage)
        .join(Listing, ListingImage.listing_id == Listing.id)
        .where(
            ListingImage.image_url == image_url,
            Listing.status == "approved",
        )
    )

    listing_image = db.scalar(statement)

    if listing_image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    image_path = resolve_image_path(listing_image.image_url)

    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    return FileResponse(
        path=image_path,
        media_type="image/webp",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/admin/listing-images/{filename}", include_in_schema=False)
def serve_admin_listing_image(
    filename: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Serve pending listing images only to authenticated administrators."""

    image_url = f"/listing-images/{filename}"

    statement = (
        select(ListingImage)
        .join(Listing, ListingImage.listing_id == Listing.id)
        .where(
            ListingImage.image_url == image_url,
            Listing.status == "pending",
        )
    )

    listing_image = db.scalar(statement)

    if listing_image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    image_path = resolve_image_path(listing_image.image_url)

    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found.",
        )

    return FileResponse(
        path=image_path,
        media_type="image/webp",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
