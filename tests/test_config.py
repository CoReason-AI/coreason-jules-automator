import os
from unittest import mock

import pytest
from pydantic import ValidationError

from coreason_jules_automator.config import Settings


def test_default_settings() -> None:
    """Test that default settings are correct."""
    # Ensure no VIBE_ env vars are set that might interfere
    with mock.patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.llm_strategy == "api"
        assert settings.extensions_enabled == ["security", "code-review"]
        assert settings.max_retries == 5


def test_env_override() -> None:
    """Test that environment variables override defaults."""
    env_vars = {
        "VIBE_LLM_STRATEGY": "local",
        "VIBE_EXTENSIONS_ENABLED": '["security"]',
        "VIBE_MAX_RETRIES": "10",
    }
    with mock.patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.llm_strategy == "local"
        assert settings.extensions_enabled == ["security"]
        assert settings.max_retries == 10


def test_env_override_invalid_strategy() -> None:
    """Test that invalid llm_strategy raises validation error."""
    env_vars = {
        "VIBE_LLM_STRATEGY": "invalid",
    }
    with mock.patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(ValidationError):
            Settings()
