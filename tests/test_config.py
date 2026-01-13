import importlib
from unittest.mock import patch

import pytest
from pydantic import ValidationError

import coreason_jules_automator.config
from coreason_jules_automator.config import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default values for settings."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy_key")
    # Ensure no other env vars interfere
    monkeypatch.delenv("VIBE_LLM_STRATEGY", raising=False)
    monkeypatch.delenv("VIBE_EXTENSIONS_ENABLED", raising=False)
    monkeypatch.delenv("VIBE_MAX_RETRIES", raising=False)

    settings = Settings()  # type: ignore[call-arg]
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
        settings = Settings()  # type: ignore[call-arg]
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
        Settings()  # type: ignore[call-arg]

    errors = excinfo.value.errors()
    fields = [e["loc"][0] for e in errors]
    assert "GITHUB_TOKEN" in fields
    assert "GOOGLE_API_KEY" in fields


def test_empty_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that empty secrets raise ValueError."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "")

    with pytest.raises(ValidationError) as excinfo:
        Settings()  # type: ignore[call-arg]

    # Verify the specific error message from the validator
    assert "Secret must not be empty" in str(excinfo.value)


def test_secrets_not_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that secrets are not exposed in repr."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "secret_token_value")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "secret_key_value")

    settings = Settings()  # type: ignore[call-arg]
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
            Settings()  # type: ignore[call-arg]

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
        settings = Settings()  # type: ignore[call-arg]
        assert settings.llm_strategy == "api"


def test_config_settings_init_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test exception during Settings initialization in config.py."""
    # Unset required env vars to force ValidationError during init
    monkeypatch.delenv("VIBE_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("VIBE_GOOGLE_API_KEY", raising=False)

    # Reload the module. Settings() instantiation should fail.
    # The try/except block in config.py should catch it.
    importlib.reload(coreason_jules_automator.config)


def test_get_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_settings returns a Settings instance."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy")

    # Reload module to get fresh classes/functions
    importlib.reload(coreason_jules_automator.config)
    from coreason_jules_automator.config import Settings as FreshSettings
    from coreason_jules_automator.config import get_settings as fresh_get_settings

    # clear lru_cache
    fresh_get_settings.cache_clear()

    s1 = fresh_get_settings()
    assert isinstance(s1, FreshSettings)

    s2 = fresh_get_settings()
    assert s1 is s2


def test_invalid_llm_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an invalid llm_strategy raises ValidationError."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "invalid_strategy")

    with pytest.raises(ValidationError) as excinfo:
        Settings()  # type: ignore[call-arg]

    assert "Input should be 'local' or 'api'" in str(excinfo.value)


def test_settings_runtime_instantiation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test instantiating Settings with runtime values overrides environment."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "env_token")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "env_key")

    # 1. Default uses env
    s1 = Settings()  # type: ignore[call-arg]
    assert s1.GITHUB_TOKEN.get_secret_value() == "env_token"

    # 2. Override via init
    s2 = Settings(GITHUB_TOKEN="override_token", GOOGLE_API_KEY="override_key")  # type: ignore[arg-type]
    assert s2.GITHUB_TOKEN.get_secret_value() == "override_token"
    assert s2.GOOGLE_API_KEY.get_secret_value() == "override_key"

    # 3. Prove s1 is unchanged (environment didn't change)
    assert s1.GITHUB_TOKEN.get_secret_value() == "env_token"
