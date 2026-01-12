import sys
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.llm.provider import LLMProvider


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBE_GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("VIBE_GOOGLE_API_KEY", "dummy")
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "api")
    get_settings.cache_clear()


def test_init_api_strategy_with_key(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization with API strategy and key present."""
    monkeypatch.setenv("VIBE_OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    mock_openai_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        provider = LLMProvider()
        assert provider.strategy == "api"
        # OpenAI class is instantiated
        mock_openai_module.OpenAI.assert_called_once()
        assert provider.client is not None


def test_init_api_strategy_openai_import_error(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization with API strategy but openai package is missing."""
    monkeypatch.setenv("VIBE_OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    # Simulate import error
    with patch.dict(sys.modules, {"openai": None}):
        with patch("coreason_jules_automator.llm.provider.logger") as mock_logger:
            mock_llama_module = MagicMock()
            # We must mock llama_cpp module first so LLMProvider can import it inside _initialize_local
            with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
                with patch("coreason_jules_automator.llm.provider.hf_hub_download", return_value="/tmp/model.gguf"):
                    _ = LLMProvider()
                    mock_logger.warning.assert_any_call("openai package not installed. Falling back to local.")
                    # Falls back to local, uses Llama from mocked module
                    mock_llama_module.Llama.assert_called_once()


def test_init_api_strategy_no_key_fallback(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to local if API key is missing."""
    monkeypatch.delenv("VIBE_OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    mock_llama_module = MagicMock()
    with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.provider.hf_hub_download", return_value="/tmp/model.gguf"):
            _ = LLMProvider()
            mock_llama_module.Llama.assert_called_once()


def test_init_local_strategy_success(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization with local strategy."""
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    # Mock find_spec to pass Settings validation
    with patch("importlib.util.find_spec", return_value=True):
        get_settings.cache_clear()  # Re-load settings with local strategy

        mock_llama_module = MagicMock()
        with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
            with patch(
                "coreason_jules_automator.llm.provider.hf_hub_download", return_value="/tmp/model.gguf"
            ) as mock_dl:
                provider = LLMProvider()
                assert provider.strategy == "local"
                mock_dl.assert_called_once()
                mock_llama_module.Llama.assert_called_once_with(model_path="/tmp/model.gguf", verbose=False)


def test_init_local_download_failure(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization when model download fails."""
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    with patch("importlib.util.find_spec", return_value=True):
        get_settings.cache_clear()

        mock_llama_module = MagicMock()
        with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
            with patch(
                "coreason_jules_automator.llm.provider.hf_hub_download", side_effect=Exception("Download failed")
            ):
                with patch("coreason_jules_automator.llm.provider.logger") as mock_logger:
                    provider = LLMProvider()
                    # Should log warning and set client to None
                    assert provider.client is None
                    mock_logger.warning.assert_called_with(
                        "Could not download model: Failed to download model: Download failed"
                    )
                    mock_llama_module.Llama.assert_not_called()


def test_init_local_strategy_missing_package_runtime_error(
    mock_settings: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test error when llama-cpp-python is missing (RuntimeError from Provider).
    """
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    # Pass Settings check
    with patch("importlib.util.find_spec", return_value=True):
        get_settings.cache_clear()

        # Fail import
        with patch.dict(sys.modules, {"llama_cpp": None}):
            with pytest.raises(RuntimeError) as excinfo:
                LLMProvider()
            assert "llama-cpp-python not installed" in str(excinfo.value)


def test_init_local_llama_fail(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization when Llama class raises exception."""
    monkeypatch.setenv("VIBE_LLM_STRATEGY", "local")

    with patch("importlib.util.find_spec", return_value=True):
        get_settings.cache_clear()

        mock_llama_module = MagicMock()
        # Mock Llama constructor raising exception
        mock_llama_module.Llama.side_effect = Exception("Model corrupt")

        with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
            with patch("coreason_jules_automator.llm.provider.hf_hub_download", return_value="/tmp/model.gguf"):
                with patch("coreason_jules_automator.llm.provider.logger") as mock_logger:
                    provider = LLMProvider()
                    assert provider.client is None
                    mock_logger.warning.assert_called_with("Failed to load local model: Model corrupt")


def test_sanitize_commit(mock_settings: None) -> None:
    """Test commit message sanitization."""
    with patch.object(LLMProvider, "_initialize_client", return_value=None):
        provider = LLMProvider()
        raw = "feat: add feature\n\nCo-authored-by: bot\nSigned-off-by: me"
        clean = provider.sanitize_commit(raw)
        assert clean == "feat: add feature"


def test_summarize_logs_openai(mock_settings: None) -> None:
    """Test summarize_logs with OpenAI client."""
    with patch.object(LLMProvider, "_initialize_client") as mock_init:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = "Summary"
        mock_init.return_value = mock_client

        provider = LLMProvider()
        summary = provider.summarize_logs("long log...")
        assert summary == "Summary"


def test_summarize_logs_local(mock_settings: None) -> None:
    """Test summarize_logs with Local client."""
    with patch.object(LLMProvider, "_initialize_client") as mock_init:
        mock_client = MagicMock()
        # Llama-cpp-python style response
        mock_client.create_chat_completion.return_value = {"choices": [{"message": {"content": "Local Summary"}}]}
        # Simulate it does NOT have 'chat' attribute (so it looks like Llama)
        del mock_client.chat
        mock_init.return_value = mock_client

        provider = LLMProvider()
        summary = provider.summarize_logs("long log...")
        assert summary == "Local Summary"


def test_summarize_logs_failure(mock_settings: None) -> None:
    """Test summarize_logs failure handling."""
    with patch.object(LLMProvider, "_initialize_client") as mock_init:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_init.return_value = mock_client

        provider = LLMProvider()
        summary = provider.summarize_logs("log")
        assert summary == "Log summarization failed. Please check the logs directly."


def test_ensure_model_downloaded_success(mock_settings: None) -> None:
    """Test successful model download."""
    with patch("coreason_jules_automator.llm.provider.hf_hub_download", return_value="/path/to/model") as mock_dl:
        with patch.object(LLMProvider, "_initialize_client", return_value=None):
            provider = LLMProvider()
            path = provider._ensure_model_downloaded()
            assert path == "/path/to/model"
            mock_dl.assert_called_once()


def test_ensure_model_downloaded_failure(mock_settings: None) -> None:
    """Test failed model download."""
    with patch("coreason_jules_automator.llm.provider.hf_hub_download", side_effect=Exception("Net error")):
        with patch.object(LLMProvider, "_initialize_client", return_value=None):
            provider = LLMProvider()
            with pytest.raises(RuntimeError) as excinfo:
                provider._ensure_model_downloaded()
            assert "Failed to download model" in str(excinfo.value)
