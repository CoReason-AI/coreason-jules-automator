from unittest.mock import patch

import pytest
from pydantic import ValidationError

from coreason_jules_automator.config import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default values for settings."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy_key")
    # Ensure no other env vars interfere
    monkeypatch.delenv("VIBE_LLM_STRATEGY", raising=False)
    monkeypatch.delenv("VIBE_EXTENSIONS_ENABLED", raising=False)
    monkeypatch.delenv("VIBE_MAX_RETRIES", raising=False)

    settings = Settings()  # type: ignore
    assert settings.llm_strategy == "api"
    assert settings.extensions_enabled == ["security", "code-review"]
    assert settings.max_retries == 5
    assert settings.GITHUB_TOKEN.get_secret_value() == "dummy_token"
    assert settings.GOOGLE_API_KEY.get_secret_value() == "dummy_key"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test overriding settings with environment variables."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy_key")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")
    monkeypatch.setenv("VIBE_EXTENSIONS_ENABLED", '["security"]')
    monkeypatch.setenv("VIBE_MAX_RETRIES", "10")

    # Mock find_spec to return True (simulating installed)
    with patch("importlib.util.find_spec", return_value=True):
        settings = Settings()  # type: ignore
        assert settings.llm_strategy == "local"
        assert settings.extensions_enabled == ["security"]
        assert settings.max_retries == 10


def test_missing_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that missing mandatory secrets raise ValidationError."""
    monkeypatch.delenv("VIBE_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("VIBE_GOOGLE_API_KEY", raising=False)
    # Also ensure env vars without prefix are not picked up if they were set in system
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings()  # type: ignore

    errors = excinfo.value.errors()
    fields = [e["loc"][0] for e in errors]
    assert "GITHUB_TOKEN" in fields
    assert "GOOGLE_API_KEY" in fields


def test_empty_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty secrets raise ValueError."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "")

    with pytest.raises(ValidationError):
        Settings()  # type: ignore


def test_secrets_not_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that secrets are not exposed in repr."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "secret_token_value")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "secret_key_value")

    settings = Settings()  # type: ignore
    repr_str = repr(settings)
    assert "secret_token_value" not in repr_str
    assert "secret_key_value" not in repr_str


def test_local_strategy_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that selecting 'local' strategy without llama_cpp installed raises ValueError."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy_key")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    # Mock find_spec to return None (simulating NOT installed)
    with patch("importlib.util.find_spec", return_value=None):
        with pytest.raises(ValidationError) as excinfo:
            Settings()  # type: ignore

        # Check that the error message contains the expected hint
        # Note: Pydantic wraps the ValueError in ValidationError
        assert "requires 'llama-cpp-python' to be installed" in str(excinfo.value)


def test_api_strategy_missing_dependency_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that selecting 'api' strategy works even if llama_cpp is missing."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy_key")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "api")

    # Mock find_spec to return None (simulating NOT installed)
    with patch("importlib.util.find_spec", return_value=None):
        settings = Settings()  # type: ignore
        assert settings.llm_strategy == "api"
