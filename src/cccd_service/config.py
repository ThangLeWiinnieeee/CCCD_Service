from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CCCD_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "WebTutorCenter CCCD Service"
    internal_secret: str = ""
    max_image_bytes: int = 8 * 1024 * 1024
    max_image_pixels: int = 24_000_000
    min_image_width: int = 640
    min_image_height: int = 400
    min_blur_score: float = 65.0
    min_brightness: float = 35.0
    max_brightness: float = 235.0
    max_glare_ratio: float = 0.18
    min_ocr_confidence: float = 0.45
    ocr_language: str = "vi"
    ocr_version: str = "PP-OCRv6"
    ocr_device: str = "cpu"
    ocr_cpu_threads: int = 4
    model_version: str = "cccd-verify-0.1.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
