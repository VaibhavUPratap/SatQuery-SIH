import os
from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_TITLE: str = "SatQuery AI API"
    API_VERSION: str = "v1"
    DEBUG: bool = True
    SATQUERY_AUTH_REQUIRED: bool = False
    SATQUERY_DEMO_USERNAME: str = "analyst.demo"
    SATQUERY_DEMO_PASSWORD: str = "satquery-demo"
    MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024
    MAX_IMAGE_PIXELS: int = 100_000_000
    MAX_QUEUED_JOBS: int = 20
    
    # Model Configuration
    VQA_MODEL_NAME: str = "Salesforce/blip-vqa-base"
    VQA_USE_FALLBACK: bool = False
    VQA_LOCAL_FILES_ONLY: bool = True
    VQA_MAX_NEW_TOKENS: int = 16
    VQA_NUM_BEAMS: int = 4
    # Kept separate from VQA so model-backed VQA does not trigger an unrelated
    # caption-model download at API startup.
    CAPTION_USE_FALLBACK: bool = True
    VQA_ADAPTER_PATH: str | None = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "checkpoints",
        "rsvqa-blip-lora",
    )

    # BigEarthNet v2.0 land-cover classification
    BIGEARTHNET_MODEL_ID: str = "BIFOLD-BigEarthNetv2-0/convmixer_768_32-all-v0.2.0"
    BIGEARTHNET_EXPECTED_BANDS: int = 12  # Sentinel-2 12 bands (the checkpoint uses S2 only)
    BIGEARTHNET_THRESHOLD: float = 0.5

    
    # Paths
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        """Accept common deployment-mode values used by local `.env` files."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
