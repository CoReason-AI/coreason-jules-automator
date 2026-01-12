# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from coreason_jules_automator.config import get_settings


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default values of configuration."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    # Unset other vars to ensure defaults are used
    monkeypatch.delenv("VIBE_LLM_STRATEGY", raising=False)
    monkeypatch.delenv("VIBE_EXTENSIONS_ENABLED", raising=False)
    monkeypatch.delenv("VIBE_MAX_RETRIES", raising=False)

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.llm_strategy == "api"
    assert settings.extensions_enabled == ["security", "code-review"]
    assert settings.max_retries == 5
    assert settings.GITHUB_TOKEN.get_secret_value() == "fake_token"
    assert settings.GOOGLE_API_KEY.get_secret_value() == "fake_key"


def test_config_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test overriding configuration via environment variables."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")
    monkeypatch.setenv("VIBE_MAX_RETRIES", "10")
    monkeypatch.setenv("VIBE_EXTENSIONS_ENABLED", '["security"]')

    # Mock llama_cpp import for local strategy check
    monkeypatch.setitem(sys.modules, "llama_cpp", MagicMock())

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.llm_strategy == "local"
    assert settings.extensions_enabled == ["security"]
    assert settings.max_retries == 10


def test_missing_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test validation error when GITHUB_TOKEN is missing."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        get_settings()

    assert "GITHUB_TOKEN" in str(excinfo.value)


def test_missing_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test validation error when GOOGLE_API_KEY is missing."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as excinfo:
        get_settings()

    assert "GOOGLE_API_KEY" in str(excinfo.value)


def test_empty_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test validation error when secrets are empty strings."""
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")

    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()

    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GOOGLE_API_KEY", "")

    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_optional_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test optional secrets loading."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-...")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.OPENAI_API_KEY is not None
    assert settings.OPENAI_API_KEY.get_secret_value() == "sk-proj-..."
    assert settings.DEEPSEEK_API_KEY is None


def test_local_strategy_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that local strategy fails if llama-cpp-python is missing."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_key")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    original_import = __import__

    def import_mock(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "llama_cpp":
            raise ImportError("Mocked ImportError")
        return original_import(name, *args, **kwargs)

    import builtins

    with monkeypatch.context() as m:
        m.setattr(builtins, "__import__", import_mock)
        get_settings.cache_clear()
        with pytest.raises(ValueError, match="llama-cpp-python"):
            get_settings()
