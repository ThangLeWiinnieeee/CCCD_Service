import hmac
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .schemas import ClaimedIdentity, VerificationResult
from .verifier import verify_cccd

router = APIRouter(prefix="/api", tags=["cccd"])
logger = logging.getLogger(__name__)
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.post("/verify", response_model=VerificationResult)
async def verify(
    front: Annotated[UploadFile, File(description="Ảnh mặt trước CCCD")],
    back: Annotated[UploadFile, File(description="Ảnh mặt sau CCCD")],
    claimed_full_name: Annotated[str | None, Form(max_length=100)] = None,
    claimed_date_of_birth: Annotated[date | None, Form()] = None,
    claimed_gender: Annotated[str | None, Form(max_length=20)] = None,
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> VerificationResult:
    _verify_secret(x_internal_secret)
    front_bytes, back_bytes = await _read_images(front, back)
    claimed = ClaimedIdentity(
        full_name=claimed_full_name,
        date_of_birth=claimed_date_of_birth,
        gender=claimed_gender,
    )
    try:
        return await run_in_threadpool(verify_cccd, front_bytes, back_bytes, claimed)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("CCCD verification failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể xử lý CCCD lúc này",
        ) from error


def _verify_secret(provided: str | None) -> None:
    expected = get_settings().internal_secret
    if expected and not hmac.compare_digest(provided or "", expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai hoặc thiếu internal secret",
        )


async def _read_images(front: UploadFile, back: UploadFile) -> tuple[bytes, bytes]:
    try:
        return await _read_image(front), await _read_image(back)
    finally:
        await front.close()
        await back.close()


async def _read_image(file: UploadFile) -> bytes:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP",
        )
    max_bytes = get_settings().max_image_bytes
    content = await file.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ảnh trống hoặc vượt quá dung lượng cho phép",
        )
    return content
