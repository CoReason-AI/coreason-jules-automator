from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from coreason_jules_automator.llm.factory import LLMFactory
from coreason_jules_automator.llm.adapters import OpenAIAdapter, LlamaAdapter


def test_get_client_api_openai_missing_import() -> None:
    """Test fallback to local when openai is missing."""
    with patch("coreason_jules_automator.llm.factory.get_settings") as mock_settings:
        mock_settings.return_value.llm_strategy = "api"
        with patch.dict("sys.modules", {"openai": None}):
            with patch("coreason_jules_automator.llm.factory.LLMFactory._initialize_local") as mock_local:
                LLMFactory.get_client()
                mock_local.assert_called_once()


def test_get_client_api_openai_key() -> None:
    """Test initialization with OpenAI key."""
    with patch("coreason_jules_automator.llm.factory.get_settings") as mock_settings:
        mock_settings.return_value.llm_strategy = "api"
        mock_settings.return_value.OPENAI_API_KEY = SecretStr("sk-test")
        mock_settings.return_value.DEEPSEEK_API_KEY = None

        with patch("openai.OpenAI") as mock_openai:
            client = LLMFactory.get_client()
            mock_openai.assert_called_with(api_key="sk-test")
            assert isinstance(client, OpenAIAdapter)


def test_get_client_api_deepseek_key() -> None:
    """Test initialization with DeepSeek key."""
    with patch("coreason_jules_automator.llm.factory.get_settings") as mock_settings:
        mock_settings.return_value.llm_strategy = "api"
        mock_settings.return_value.OPENAI_API_KEY = None
        mock_settings.return_value.DEEPSEEK_API_KEY = SecretStr("sk-deepseek")

        with patch("openai.OpenAI") as mock_openai:
            client = LLMFactory.get_client()
            mock_openai.assert_called_with(api_key="sk-deepseek", base_url="https://api.deepseek.com")
            assert isinstance(client, OpenAIAdapter)


def test_get_client_api_no_keys() -> None:
    """Test fallback to local when no keys are present."""
    with patch("coreason_jules_automator.llm.factory.get_settings") as mock_settings:
        mock_settings.return_value.llm_strategy = "api"
        mock_settings.return_value.OPENAI_API_KEY = None
        mock_settings.return_value.DEEPSEEK_API_KEY = None

        with patch("coreason_jules_automator.llm.factory.LLMFactory._initialize_local") as mock_local:
            LLMFactory.get_client()
            mock_local.assert_called_once()


def test_initialize_local_success() -> None:
    """Test successful local initialization."""
    with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
        mock_manager.return_value.ensure_model_downloaded.return_value = "/path/to/model"
        # Mock sys.modules so 'llama_cpp' exists
        mock_llama_module = MagicMock()
        with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
            client = LLMFactory._initialize_local()
            mock_llama_module.Llama.assert_called_with(model_path="/path/to/model", verbose=False)
            assert isinstance(client, LlamaAdapter)


def test_initialize_local_download_failure() -> None:
    """Test failure when model download fails."""
    mock_llama_module = MagicMock()
    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
            mock_manager.return_value.ensure_model_downloaded.side_effect = RuntimeError("Download failed")
            client = LLMFactory._initialize_local()
            assert client is None


def test_initialize_local_import_error() -> None:
    """Test failure when llama_cpp is missing."""
    with patch.dict("sys.modules", {"llama_cpp": None}):
        # We also need to reload the module or patch where it's imported if it was already imported,
        # but since we are using import inside function, this should work.
        with pytest.raises(RuntimeError, match="llama-cpp-python not installed"):
            LLMFactory._initialize_local()


def test_initialize_local_load_failure() -> None:
    """Test failure when loading model fails."""
    mock_llama_module = MagicMock()
    mock_llama_module.Llama.side_effect = Exception("Load failed")

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
            mock_manager.return_value.ensure_model_downloaded.return_value = "/path/to/model"
            client = LLMFactory._initialize_local()
            assert client is None
