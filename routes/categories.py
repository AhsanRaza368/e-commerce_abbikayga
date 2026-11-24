from routes.auth import get_current_admin
from schemas import CategoryCreate, CategoryPublic
from models import Category, AdminUser
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status


router = APIRouter(
    prefix="/admin/categories",
    tags=["Admin Category Management"],
)


@router.post("/", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Create a category. Only authenticated administrators can do this."""

    name = category_data.name.strip()
    slug = category_data.slug.strip().lower()

    existing_category = db.scalar(
        select(Category).where(
            (Category.name == name) | (Category.slug == slug)
        )
    )

    if existing_category:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name or slug already exists.",
        )

    category = Category(
        name=name,
        slug=slug,
        is_active=True,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.get("/", response_model=list[CategoryPublic])
def get_all_categories(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List all categories, including inactive ones."""

    statement = select(Category).order_by(Category.name.asc())

    return db.scalars(statement).all()


@router.patch("/{category_id}/status")
def update_category_status(
    category_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Activate or deactivate a category."""

    category = db.get(Category, category_id)

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    category.is_active = is_active

    db.commit()
    db.refresh(category)

    return {
        "message": "Category status updated successfully.",
        "id": category.id,
        "name": category.name,
        "is_active": category.is_active,
    }
