from fastapi import FastAPI

from . import __version__
from .api import router
from .config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "OCR và kiểm tra tính nhất quán của CCCD Việt Nam. "
        "Kết quả không thay thế xác minh từ cơ quan phát hành."
    ),
)
app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
