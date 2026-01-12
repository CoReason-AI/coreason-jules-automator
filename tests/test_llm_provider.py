from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.llm.provider import LLMProvider


@pytest.fixture
def mock_settings() -> Any:
    """
    Fixture to mock Settings class and clear get_settings cache.
    This prevents ValidationError when env vars are missing.
    """
    with patch("coreason_jules_automator.config.Settings") as MockSettings:
        settings_instance = MagicMock()
        settings_instance.llm_strategy = "api"
        # Set default behavior for secrets
        settings_instance.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"
        MockSettings.return_value = settings_instance

        # Clear cache to ensure get_settings uses the mocked Settings class
        get_settings.cache_clear()

        yield settings_instance

        get_settings.cache_clear()


def test_sanitize_commit(mock_settings: Any) -> None:
    """Test commit message sanitization."""
    # We need to ensure _initialize_client doesn't fail or return something that breaks
    # But since we mock settings, initialization should proceed fine.
    # However, to be safe/fast, we can mock _initialize_client too.
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client", return_value=None):
        provider = LLMProvider()
        original = (
            "feat: add new feature\n\n"
            "This adds a cool feature.\n\n"
            "Co-authored-by: Bot <bot@example.com>\n"
            "Signed-off-by: User <user@example.com>"
        )
        expected = "feat: add new feature\n\nThis adds a cool feature."
        assert provider.sanitize_commit(original) == expected


def test_init_api_success(mock_settings: Any) -> None:
    """Test initialization with API strategy and key."""
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"

    with patch("openai.OpenAI") as MockOpenAI:
        provider = LLMProvider()
        assert provider.client is not None
        MockOpenAI.assert_called_once_with(api_key="sk-test")


def test_init_api_import_error(mock_settings: Any) -> None:
    """Test fallback to local if openai not installed."""
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"

    # Simulate ImportError for openai
    with patch.dict("sys.modules", {"openai": None}):
        with patch.object(LLMProvider, "_initialize_local") as mock_local:
            LLMProvider()
            mock_local.assert_called_once()


def test_init_fallback_to_local_no_key(mock_settings: Any) -> None:
    """Test fallback to local if API key missing."""
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = None

    with patch.object(LLMProvider, "_initialize_local") as mock_local:
        LLMProvider()
        mock_local.assert_called_once()


def test_init_local_success(mock_settings: Any) -> None:
    """Test local initialization."""
    mock_settings.llm_strategy = "local"

    # Mock llama_cpp module existence and Llama class
    mock_llama_module = MagicMock()
    # When instantiated, Llama class returns a mock client
    mock_llama_client = MagicMock()
    mock_llama_module.Llama.return_value = mock_llama_client

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        provider = LLMProvider()
        assert provider.client is mock_llama_client
        mock_llama_module.Llama.assert_called_once()


def test_init_local_import_error(mock_settings: Any) -> None:
    """Test local initialization failure due to missing dependency."""
    mock_settings.llm_strategy = "local"

    # Simulate missing llama_cpp
    with patch.dict("sys.modules", {"llama_cpp": None}):
        with pytest.raises(RuntimeError) as excinfo:
            LLMProvider()
        assert "llama-cpp-python not installed" in str(excinfo.value)


def test_init_local_exception(mock_settings: Any) -> None:
    """Test local initialization failure due to other error (e.g. model missing)."""
    mock_settings.llm_strategy = "local"

    mock_llama_module = MagicMock()
    # Configure Llama to raise Exception
    mock_llama_module.Llama.side_effect = Exception("Model not found")

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        provider = LLMProvider()
        assert provider.client is None
        # Should log warning


def test_summarize_logs_openai(mock_settings: Any) -> None:
    """Test summarize_logs with OpenAI client."""
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"

    with patch("openai.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "Summary."
        MockOpenAI.return_value = mock_client

        provider = LLMProvider()
        summary = provider.summarize_logs("long error log")
        assert summary == "Summary."


def test_summarize_logs_llama(mock_settings: Any) -> None:
    """Test summarize_logs with Llama client."""
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client") as mock_init:
        mock_client = MagicMock()
        # IMPORTANT: Ensure 'chat' attribute does NOT exist so it falls through to 'create_chat_completion'
        del mock_client.chat

        mock_client.create_chat_completion.return_value = {"choices": [{"message": {"content": "Local Summary."}}]}
        mock_init.return_value = mock_client

        provider = LLMProvider()
        summary = provider.summarize_logs("error")
        assert summary == "Local Summary."


def test_summarize_logs_exception(mock_settings: Any) -> None:
    """Test exception during summarization."""
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client") as mock_init:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_init.return_value = mock_client

        provider = LLMProvider()
        assert provider.summarize_logs("err") == "Log summarization failed. Please check the logs directly."


def test_summarize_logs_failure(mock_settings: Any) -> None:
    """Test failure in summarization (no client)."""
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client", return_value=None):
        provider = LLMProvider()
        assert provider.summarize_logs("err") == "Log summarization failed. Please check the logs directly."
