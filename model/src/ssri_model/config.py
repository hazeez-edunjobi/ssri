import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelSettings:
    """Placeholder settings for future ML pipeline configuration."""

    model_name: str = "ssri-model"
    log_level: str = "INFO"
    data_dir: str = "./data"
    checkpoint_dir: str = "./checkpoints"
    random_seed: int = 42

    @classmethod
    def from_env(cls) -> "ModelSettings":
        return cls(
            model_name=os.getenv("MODEL_NAME", "ssri-model"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            data_dir=os.getenv("MODEL_DATA_DIR", "./data"),
            checkpoint_dir=os.getenv("MODEL_CHECKPOINT_DIR", "./checkpoints"),
            random_seed=int(os.getenv("MODEL_RANDOM_SEED", "42")),
        )


@lru_cache
def get_settings() -> ModelSettings:
    """Return cached model settings."""
    return ModelSettings.from_env()
