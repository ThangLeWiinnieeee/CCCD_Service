import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import __version__
from .api import router
from .config import Settings, get_settings
from .ocr import get_ocr_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.is_production:
            await run_in_threadpool(get_ocr_engine)
        yield

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "OCR và kiểm tra tính nhất quán của CCCD Việt Nam. "
            "Kết quả không thay thế xác minh từ cơ quan phát hành."
        ),
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(router)

    @app.middleware("http")
    async def require_internal_secret(request: Request, call_next):
        expected = settings.internal_secret
        provided = request.headers.get("X-Internal-Secret", "")
        if (
            request.url.path.startswith("/api/")
            and expected
            and not hmac.compare_digest(provided.encode(), expected.encode())
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Sai hoặc thiếu internal secret"},
            )
        return await call_next(request)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
