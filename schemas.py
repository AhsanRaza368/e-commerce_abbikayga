
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True)]
PhoneText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=7, max_length=30),
]


class CategoryCreate(BaseModel):
    name: ShortText = Field(min_length=2, max_length=80)
    slug: ShortText = Field(min_length=2, max_length=100)


class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_active: bool


class ListingCreate(BaseModel):
    title: ShortText = Field(min_length=5, max_length=150)
    description: ShortText = Field(min_length=20, max_length=5000)
    category_id: int = Field(gt=0)

    listing_type: Literal["sale", "free"] = "sale"
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    condition: Literal[
        "new", "like_new", "good", "fair", "for_parts"
    ] | None = None

    city: ShortText = Field(min_length=2, max_length=100)
    location_details: str | None = Field(default=None, max_length=200)

    seller_name: ShortText = Field(min_length=2, max_length=100)
    seller_phone: PhoneText

    @model_validator(mode="after")
    def validate_price(self):
        if self.listing_type == "sale" and self.price is None:
            raise ValueError("A price is required for items offered for sale.")

        if self.listing_type == "free":
            self.price = None

        return self


class ListingImagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    position: int


class ListingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category_id: int
    listing_type: str
    price: Decimal | None
    condition: str | None
    city: str
    location_details: str | None
    seller_name: str
    seller_phone: str
    status: str
    created_at: datetime
    images: list[ListingImagePublic] = Field(default_factory=list)


class AdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool


class ListingModeration(BaseModel):
    status: Literal["approved", "rejected", "removed"]
    rejection_reason: str | None = Field(default=None, max_length=2000)


class ReportCreate(BaseModel):
    reason: ShortText = Field(min_length=3, max_length=100)
    details: str | None = Field(default=None, max_length=3000)
    reporter_contact: str | None = Field(default=None, max_length=255)


class CategoryCreate(BaseModel):
    name: str
    slug: str


class CategoryPublic(BaseModel):
    id: int
    name: str
    slug: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ReportReceipt(BaseModel):
    """Confirmation returned after a public report is submitted."""

    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportPublic(BaseModel):
    """Report information visible to administrators."""

    id: int
    listing_id: int
    listing_title: str
    reason: str
    details: str | None
    reporter_contact: str | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportStatusUpdate(BaseModel):
    """Allowed report status changes."""

    status: Literal["open", "reviewed", "resolved", "dismissed"]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)


class CustomerSignup(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class CustomerSignupVerification(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class CustomerSignupResend(BaseModel):
    email: EmailStr


class CustomerLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class CustomerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str | None
    profile_picture_url: str | None
    is_active: bool
    created_at: datetime


class CustomerProfileUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )
    email: EmailStr | None = None
    phone: str | None = Field(
        default=None,
        max_length=30,
    )


class CustomerPasswordResetRequest(BaseModel):
    email: EmailStr


class CustomerPasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)
