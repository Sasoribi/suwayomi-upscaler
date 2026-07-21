"""Configuration from environment variables with sensible defaults."""
import os


class Config:
    UPSCALE_ENGINE: str = os.getenv("UPSCALE_ENGINE", "realcugan")
    UPSCALE_SCALE: int = int(os.getenv("UPSCALE_SCALE", "2"))
    UPSCALE_THRESHOLD: int = int(os.getenv("UPSCALE_THRESHOLD", "2048"))
    CACHE_MAX_GB: int = int(os.getenv("CACHE_MAX_GB", "20"))
    CACHE_DIR: str = os.getenv("CACHE_DIR", os.path.join(os.getcwd(), "cache"))
    SUWAYOMI_URL: str = os.getenv("SUWAYOMI_URL", "http://127.0.0.1:4567")
    SUWAYOMI_TIMEOUT: int = int(os.getenv("SUWAYOMI_TIMEOUT", "30"))
    FETCH_CONCURRENCY: int = int(os.getenv("FETCH_CONCURRENCY", "20"))
    PORT: int = int(os.getenv("PORT", "8765"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        errors = []
        if cls.UPSCALE_ENGINE not in ("realcugan", "waifu2x", "realesrgan"):
            errors.append(f"Unknown UPSCALE_ENGINE: {cls.UPSCALE_ENGINE}")
        if cls.UPSCALE_SCALE not in (2, 3, 4):
            errors.append(f"UPSCALE_SCALE must be 2, 3, or 4, got: {cls.UPSCALE_SCALE}")
        if cls.UPSCALE_THRESHOLD < 0:
            errors.append(f"UPSCALE_THRESHOLD must be >= 0, got: {cls.UPSCALE_THRESHOLD}")
        return errors
