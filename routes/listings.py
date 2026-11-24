from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Category, Listing
from schemas import ListingCreate, ListingPublic

from fastapi import File, Form, UploadFile, status
from pydantic import ValidationError
from models import ListingImage
from services.uploads import resolve_image_path, save_listing_image
from fastapi import Request, Response
from services.rate_limiter import limiter
from models import Customer
from routes.customers import get_current_customer


router = APIRouter(prefix="/listings", tags=["Public Listings"])


@router.get("/", response_model=list[ListingPublic])
def get_listings(
    keyword: str | None = Query(default=None, min_length=1, max_length=100),
    category_id: int | None = Query(default=None, gt=0),
    city: str | None = Query(default=None, min_length=1, max_length=100),
    listing_type: str | None = Query(default=None, pattern="^(sale|free)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return approved listings with optional search filters."""

    statement = (
        select(Listing)
        .options(
            selectinload(Listing.images),
            selectinload(Listing.category),
        )
        .where(Listing.status == "approved")
    )

    if keyword:
        search_term = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                Listing.title.ilike(search_term),
                Listing.description.ilike(search_term),
            )
        )

    if category_id is not None:
        statement = statement.where(Listing.category_id == category_id)

    if city:
        statement = statement.where(Listing.city.ilike(city.strip()))

    if listing_type:
        statement = statement.where(Listing.listing_type == listing_type)

    statement = (
        statement
        .order_by(Listing.created_at.desc(), Listing.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return db.scalars(statement).all()


@router.get("/categories/active")
def get_active_categories(db: Session = Depends(get_db)):
    """Return active categories for the public listing form."""

    statement = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc())
    )

    categories = db.scalars(statement).all()

    return [
        {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
        }
        for category in categories
    ]


@router.post(
    "/with-images",
    response_model=ListingPublic,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/hour")
async def create_listing_with_images(
    request: Request,
    response: Response,
    title: str = Form(...),
    description: str = Form(...),
    category_id: int = Form(...),
    listing_type: str = Form("sale"),
    price: str | None = Form(None),
    condition: str = Form(...),
    city: str = Form(...),
    location_details: str = Form(...),
    seller_name: str = Form(...),
    seller_phone: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Create a pending listing and optionally attach up to three images."""

    uploaded_images = [image for image in images if image.filename]

    # Close empty file inputs.
    for image in images:
        if not image.filename:
            await image.close()

    if len(uploaded_images) > 3:
        for image in uploaded_images:
            await image.close()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A listing can have at most 3 images.",
        )

    try:
        listing_data = ListingCreate.model_validate({
            "title": title,
            "description": description,
            "category_id": category_id,
            "listing_type": listing_type,
            "price": price.strip() if price and price.strip() else None,
            "condition": condition,
            "city": city,
            "location_details": location_details,
            "seller_name": seller_name,
            "seller_phone": seller_phone,
        })
    except ValidationError as exc:
        for image in uploaded_images:
            await image.close()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc

    category = db.get(Category, listing_data.category_id)

    if category is None or not category.is_active:
        for image in uploaded_images:
            await image.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected category is unavailable.",
        )

    saved_urls: list[str] = []

    try:
        # Validate and save the files before storing their URLs.
        for image in uploaded_images:
            saved_urls.append(await save_listing_image(image))

        listing = Listing(
            **listing_data.model_dump(),
            customer_id=current_customer.id,
            status="pending",


        )
        db.add(listing)
        db.flush()

        for position, image_url in enumerate(saved_urls, start=1):
            db.add(
                ListingImage(
                    listing_id=listing.id,
                    image_url=image_url,
                    position=position,
                )
            )

        db.commit()

    except Exception:
        db.rollback()

        # Delete files if the database operation fails.
        for image_url in saved_urls:
            path = resolve_image_path(image_url)
            if path is not None:
                path.unlink(missing_ok=True)

        raise

    finally:
        for image in uploaded_images:
            await image.close()

    # Load images explicitly for the response.
    result = db.scalar(
        select(Listing)
        .options(selectinload(Listing.images))
        .where(Listing.id == listing.id)
    )
    return result


@router.get("/{listing_id}", response_model=ListingPublic)
def get_listing(
    listing_id: int,
    db: Session = Depends(get_db),
):
    """Return one approved listing, including seller contact details."""

    statement = (
        select(Listing)
        .options(
            selectinload(Listing.images),
            selectinload(Listing.category),
        )
        .where(
            Listing.id == listing_id,
            Listing.status == "approved",
        )
    )

    listing = db.scalar(statement)

    if listing is None:
        raise HTTPException(
            status_code=404,
            detail="Listing not found.",
        )

    return listing


@router.post("/", response_model=ListingPublic, status_code=201)
@limiter.limit("5/hour")
def create_listing(
    request: Request,
    response: Response,
    listing_data: ListingCreate,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Submit an advertisement for administrator moderation."""

    category = db.get(Category, listing_data.category_id)

    if category is None or not category.is_active:
        raise HTTPException(
            status_code=400,
            detail="Selected category is unavailable.",
        )

    listing = Listing(
        **listing_data.model_dump(),
        customer_id=current_customer.id,
        status="pending",

    )

    db.add(listing)
    db.commit()
    db.refresh(listing)

    return listing
