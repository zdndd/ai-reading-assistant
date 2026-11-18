from app.core.config import Settings


def test_blank_gemini_key_is_not_configured(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, gemini_api_key="")

    assert settings.has_gemini_api_key is False
