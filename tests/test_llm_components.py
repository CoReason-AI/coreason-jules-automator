import sys
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from coreason_jules_automator.config import get_settings, Settings
from coreason_jules_automator.llm.factory import LLMFactory
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.model_manager import ModelManager


# --- LLMFactory Tests ---


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to reset settings for each test."""
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "gemini_test")


def test_factory_get_client_api_openai(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory returns OpenAI client when API key is present."""
    monkeypatch.setenv("VIBE_OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    settings = get_settings()

    mock_openai_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        LLMFactory().get_client(settings)
        # Verify AsyncOpenAI was called
        mock_openai_module.AsyncOpenAI.assert_called()


def test_factory_get_client_api_deepseek(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory returns OpenAI client configured for DeepSeek."""
    monkeypatch.delenv("VIBE_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VIBE_DEEPSEEK_API_KEY", "sk-deepseek")
    get_settings.cache_clear()
    settings = get_settings()

    mock_openai_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        LLMFactory().get_client(settings)
        call_kwargs = mock_openai_module.AsyncOpenAI.call_args[1]
        assert call_kwargs["base_url"] == "https://api.deepseek.com"


def test_factory_get_client_local_success(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory returns Local client when strategy is local or api fallback."""
    # We need to mock import checks in Settings config validation
    with patch("importlib.util.find_spec", return_value=True):
        monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")
        get_settings.cache_clear()
        settings = get_settings()

    mock_llama_module = MagicMock()
    # Mock ModelManager to avoid download
    with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_mm_cls:
        mock_mm = mock_mm_cls.return_value
        mock_mm.ensure_model_downloaded.return_value = "/tmp/model.gguf"

        with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
            LLMFactory().get_client(settings)
            mock_llama_module.Llama.assert_called()


def test_factory_get_client_local_import_error(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory raises error when llama_cpp is missing."""
    # Mock validation error during settings creation
    with patch("importlib.util.find_spec", return_value=None):
        monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")
        get_settings.cache_clear()
        with pytest.raises(ValidationError):  # Pydantic validation error
            get_settings()

    # Also test the runtime check in factory if settings passed check (e.g. uninstalled after start?)
    # or if we bypass validation.

    # Let's bypass validation for this specific test to reach factory logic
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "api")  # default to api so it validates
    get_settings.cache_clear()
    settings = get_settings()

    # Now force it to fall back to local in factory by making API key missing/invalid?
    # Or just call _initialize_local directly if possible, but it's private.
    # LLMFactory logic: if strategy=api but no keys, warn and fallback to local.
    monkeypatch.delenv("VIBE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VIBE_DEEPSEEK_API_KEY", raising=False)
    # Re-init settings to clear keys
    get_settings.cache_clear()
    settings = get_settings()

    with patch.dict(sys.modules, {"llama_cpp": None}):
        with pytest.raises(RuntimeError, match="llama-cpp-python not installed"):
            LLMFactory().get_client(settings)


def test_model_manager_download(tmp_path: Exception) -> None:
    """Test ModelManager downloads model."""
    # We need to patch where ModelManager calls hf_hub_download
    with patch("coreason_jules_automator.llm.model_manager.hf_hub_download") as mock_dl:
        mock_dl.return_value = str(tmp_path)
        mm = ModelManager()
        path = mm.ensure_model_downloaded()
        assert path == str(tmp_path)


# --- JanitorService Tests ---


@pytest.mark.asyncio
async def test_janitor_summarize_logs_success() -> None:
    """Test summarize_logs with a valid LLMClient."""
    mock_client = MagicMock()
    # Mock the complete method
    mock_client.complete = AsyncMock(return_value="Summary")

    janitor = JanitorService(llm_client=mock_client)
    summary = await janitor.summarize_logs("long log...")
    assert summary == "Summary"


@pytest.mark.asyncio
async def test_janitor_summarize_logs_failure() -> None:
    """Test summarize_logs failure handling."""
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(side_effect=Exception("API Error"))

    janitor = JanitorService(llm_client=mock_client)
    summary = await janitor.summarize_logs("log")
    assert summary == "Log summarization failed. Please check the logs directly."
