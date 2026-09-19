from ssri_model.config import ModelSettings, get_settings


def test_settings_defaults() -> None:
    settings = ModelSettings()

    assert settings.model_name == "ssri-model"
    assert settings.log_level == "INFO"


def test_get_settings_returns_cached_instance() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings is get_settings()
