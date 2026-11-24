
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes.admin import router as admin_listings_router
from routes.auth import router as auth_router
from routes.listings import router as listings_router
from routes.categories import router as categories_router
from routes.reports import router as reports_router
from routes.images import router as images_router
from fastapi.openapi.utils import get_openapi
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from services.rate_limiter import limiter
from routes.customers import router as customers_router

app = FastAPI(
    title="AbbiKayGa",
    description="Classified marketplace for buying, selling, and giving away items.",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

# Register application routers.
app.include_router(auth_router)
app.include_router(listings_router)
app.include_router(categories_router)
app.include_router(admin_listings_router)
app.include_router(reports_router)
app.include_router(images_router)
app.include_router(customers_router)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/admin/login", include_in_schema=False)
def admin_login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={},
    )


@app.get("/admin/forgot-password", include_in_schema=False)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={},
    )


@app.get("/admin/reset-password", include_in_schema=False)
def reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={},
    )


@app.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={},
    )


@app.get("/customer/signup", include_in_schema=False)
def customer_signup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_signup.html",
        context={},
    )


@app.get("/customer/verify-email", include_in_schema=False)
def customer_verify_email_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_verify_email.html",
        context={},
    )


@app.get("/customer/login", include_in_schema=False)
def customer_login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_login.html",
        context={},
    )


@app.get("/customer/forgot-password", include_in_schema=False)
def customer_forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_forgot_password.html",
        context={},
    )


@app.get("/customer/reset-password", include_in_schema=False)
def customer_reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_reset_password.html",
        context={},
    )


@app.get("/customer/my-listings", include_in_schema=False)
def customer_listings_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_listings.html",
        context={},
    )


@app.get("/customer/profile", include_in_schema=False)
def customer_profile_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customer_profile.html",
        context={},
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}


def custom_openapi():
    """Make Swagger UI display file pickers for uploaded images."""

    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    for component in schema.get("components", {}).get("schemas", {}).values():
        for prop in component.get("properties", {}).values():

            # Support a single uploaded file.
            if prop.get("contentMediaType") == "application/octet-stream":
                prop.pop("contentMediaType", None)
                prop["format"] = "binary"

            # Support arrays of uploaded files, such as listing images.
            items = prop.get("items")

            if (
                isinstance(items, dict)
                and items.get("contentMediaType") == "application/octet-stream"
            ):
                items.pop("contentMediaType", None)
                items["format"] = "binary"

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)
