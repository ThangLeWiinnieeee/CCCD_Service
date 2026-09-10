FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser

# Mặc định tải model ngay lúc build để container production không phụ thuộc mạng khi khởi động.
ARG PRELOAD_MODELS=true
RUN if [ "$PRELOAD_MODELS" = "true" ]; then \
      python -c "from cccd_service.ocr import get_ocr_engine; get_ocr_engine()"; \
    fi

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8002') + '/health', timeout=3)"

CMD ["sh", "-c", "exec uvicorn cccd_service.main:app --host 0.0.0.0 --port \"${PORT:-8002}\" --workers 1 --no-server-header"]
