from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.llm.provider import LLMProvider


def test_sanitize_commit() -> None:
    """Test commit message sanitization."""
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


def test_init_api_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization with API strategy and key."""
    # Patch settings via get_settings
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "api"
        mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"
        mock_get_settings.return_value = mock_settings

        with patch("openai.OpenAI") as MockOpenAI:
            provider = LLMProvider()
            assert provider.client is not None
            MockOpenAI.assert_called_once_with(api_key="sk-test")


def test_init_api_import_error() -> None:
    """Test fallback to local if openai not installed."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "api"
        mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"
        mock_get_settings.return_value = mock_settings

        # Simulate ImportError
        with patch.dict("sys.modules", {"openai": None}):
            with patch.object(LLMProvider, "_initialize_local") as mock_local:
                LLMProvider()
                mock_local.assert_called_once()


def test_init_fallback_to_local_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to local if API key missing."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "api"
        mock_settings.OPENAI_API_KEY = None
        mock_get_settings.return_value = mock_settings

        with patch.object(LLMProvider, "_initialize_local") as mock_local:
            LLMProvider()
            mock_local.assert_called_once()


def test_init_local_success() -> None:
    """Test local initialization."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "local"
        mock_get_settings.return_value = mock_settings

        with patch("llama_cpp.Llama") as MockLlama:
            provider = LLMProvider()
            assert provider.client is not None
            MockLlama.assert_called_once()


def test_init_local_import_error() -> None:
    """Test local initialization failure due to missing dependency."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "local"
        mock_get_settings.return_value = mock_settings

        with patch.dict("sys.modules", {"llama_cpp": None}):
            with pytest.raises(RuntimeError) as excinfo:
                LLMProvider()
            assert "llama-cpp-python not installed" in str(excinfo.value)


def test_init_local_exception() -> None:
    """Test local initialization failure due to other error (e.g. model missing)."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "local"
        mock_get_settings.return_value = mock_settings

        # We need llama_cpp to be present but raising exception
        with patch("llama_cpp.Llama", side_effect=Exception("Model not found")):
            provider = LLMProvider()
            assert provider.client is None
            # Should log warning


def test_summarize_logs_openai() -> None:
    """Test summarize_logs with OpenAI client."""
    with patch("coreason_jules_automator.llm.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.llm_strategy = "api"
        mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "sk-test"
        mock_get_settings.return_value = mock_settings

        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value.choices[0].message.content = "Summary."
            MockOpenAI.return_value = mock_client

            provider = LLMProvider()
            summary = provider.summarize_logs("long error log")
            assert summary == "Summary."


def test_summarize_logs_llama() -> None:
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


def test_summarize_logs_exception() -> None:
    """Test exception during summarization."""
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client") as mock_init:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_init.return_value = mock_client

        provider = LLMProvider()
        assert provider.summarize_logs("err") == "Log summarization failed. Please check the logs directly."


def test_summarize_logs_failure() -> None:
    """Test failure in summarization (no client)."""
    with patch("coreason_jules_automator.llm.provider.LLMProvider._initialize_client", return_value=None):
        provider = LLMProvider()
        assert provider.summarize_logs("err") == "Log summarization failed. Please check the logs directly."
