
import io
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError


# Store uploads outside the public static directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "media" / "listings"
PROFILE_UPLOAD_DIR = PROJECT_ROOT / "media" / "customer-profiles"

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB per image
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

# The browser/API uses this URL; files remain outside static/.
IMAGE_URL_PREFIX = "/listing-images/"
PROFILE_IMAGE_URL_PREFIX = "/customer-profile-images/"


async def save_listing_image(upload: UploadFile) -> str:
    """Validate, normalize, and safely store one listing image.

    Returns a URL handled by the application's protected image endpoint.
    The route that serves this URL must check whether the listing is approved.
    """

    return await _save_image(
        upload,
        UPLOAD_DIR,
        IMAGE_URL_PREFIX,
        "Each image must be 5 MB or smaller.",
    )


async def normalize_customer_profile_picture(upload: UploadFile) -> bytes:
    """Validate and normalize a customer profile picture for database storage."""

    return await _normalize_image_upload(
        upload,
        "The image must be 5 MB or smaller.",
    )


async def _save_image(
    upload: UploadFile,
    upload_dir: Path,
    image_url_prefix: str,
    oversized_detail: str,
) -> str:
    image_data = await _normalize_image_upload(upload, oversized_detail)
    filename = f"{uuid.uuid4().hex}.webp"
    upload_dir.mkdir(parents=True, exist_ok=True)

    final_path = upload_dir / filename
    temporary_path = upload_dir / f".{filename}.tmp"

    try:
        temporary_path.write_bytes(image_data)
        os.replace(temporary_path, final_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return f"{image_url_prefix}{filename}"


async def _normalize_image_upload(
    upload: UploadFile,
    oversized_detail: str,
) -> bytes:
    try:
        contents = await upload.read(MAX_IMAGE_SIZE_BYTES + 1)

        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded image is empty.",
            )

        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=oversized_detail,
            )

        with Image.open(io.BytesIO(contents)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only JPEG, PNG, and WebP images are allowed.",
                )

            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="The image dimensions are too large.",
                )

            if getattr(source, "n_frames", 1) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Animated images are not supported.",
                )

            source.verify()

        with Image.open(io.BytesIO(contents)) as source:
            image = ImageOps.exif_transpose(source)

            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                normalized = background
            else:
                normalized = image.convert("RGB")

            output = io.BytesIO()
            normalized.save(
                output,
                format="WEBP",
                quality=85,
                method=6,
            )
            return output.getvalue()

    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid supported image.",
        ) from exc
    finally:
        await upload.close()


def resolve_image_path(image_url: str) -> Path | None:
    """Resolve a stored image URL to a local file without accepting paths."""

    return _resolve_image_path(image_url, IMAGE_URL_PREFIX, UPLOAD_DIR)


def resolve_profile_image_path(image_url: str) -> Path | None:
    """Resolve a customer profile image URL to its stored file."""

    return _resolve_image_path(
        image_url,
        PROFILE_IMAGE_URL_PREFIX,
        PROFILE_UPLOAD_DIR,
    )


def _resolve_image_path(
    image_url: str,
    image_url_prefix: str,
    upload_dir: Path,
) -> Path | None:
    if not image_url.startswith(image_url_prefix):
        return None

    filename = image_url[len(image_url_prefix):]

    # Only accept generated UUID filenames, never user-supplied paths.
    if not re.fullmatch(r"[0-9a-f]{32}\.webp", filename):
        return None

    path = (upload_dir / filename).resolve()

    if path.parent != upload_dir.resolve() or not path.is_file():
        return None

    return path
