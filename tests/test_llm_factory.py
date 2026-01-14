from unittest.mock import MagicMock, patch

import pytest
from coreason_jules_automator.config import Settings
from coreason_jules_automator.llm.adapters import LlamaAdapter, OpenAIAdapter
from coreason_jules_automator.llm.factory import LLMFactory
from pydantic import SecretStr


def test_get_client_api_openai_missing_import() -> None:
    """Test fallback to local when openai is missing."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"

    with patch.dict("sys.modules", {"openai": None}):
        with patch("coreason_jules_automator.llm.factory.LLMFactory._initialize_local") as mock_local:
            factory = LLMFactory()
            factory.get_client(mock_settings)
            mock_local.assert_called_once_with(mock_settings)


def test_get_client_api_openai_key() -> None:
    """Test initialization with OpenAI key."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = SecretStr("sk-test")
    mock_settings.DEEPSEEK_API_KEY = None

    with patch("openai.OpenAI") as mock_openai:
        factory = LLMFactory()
        client = factory.get_client(mock_settings)
        mock_openai.assert_called_with(api_key="sk-test")
        assert isinstance(client, OpenAIAdapter)


def test_get_client_api_deepseek_key() -> None:
    """Test initialization with DeepSeek key."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = None
    mock_settings.DEEPSEEK_API_KEY = SecretStr("sk-deepseek")

    with patch("openai.OpenAI") as mock_openai:
        factory = LLMFactory()
        client = factory.get_client(mock_settings)
        mock_openai.assert_called_with(api_key="sk-deepseek", base_url="https://api.deepseek.com")
        assert isinstance(client, OpenAIAdapter)


def test_get_client_api_no_keys() -> None:
    """Test fallback to local when no keys are present."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = None
    mock_settings.DEEPSEEK_API_KEY = None

    with patch("coreason_jules_automator.llm.factory.LLMFactory._initialize_local") as mock_local:
        factory = LLMFactory()
        factory.get_client(mock_settings)
        mock_local.assert_called_once_with(mock_settings)


def test_initialize_local_success() -> None:
    """Test successful local initialization."""
    mock_settings = MagicMock(spec=Settings)

    with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
        mock_manager.return_value.ensure_model_downloaded.return_value = "/path/to/model"
        # Mock sys.modules so 'llama_cpp' exists
        mock_llama_module = MagicMock()
        with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
            factory = LLMFactory()
            client = factory._initialize_local(mock_settings)
            mock_llama_module.Llama.assert_called_with(model_path="/path/to/model", verbose=False)
            assert isinstance(client, LlamaAdapter)


def test_initialize_local_download_failure() -> None:
    """Test failure when model download fails."""
    mock_settings = MagicMock(spec=Settings)

    mock_llama_module = MagicMock()
    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
            mock_manager.return_value.ensure_model_downloaded.side_effect = RuntimeError("Download failed")
            factory = LLMFactory()
            client = factory._initialize_local(mock_settings)
            assert client is None


def test_initialize_local_import_error() -> None:
    """Test failure when llama_cpp is missing."""
    mock_settings = MagicMock(spec=Settings)

    with patch.dict("sys.modules", {"llama_cpp": None}):
        with pytest.raises(RuntimeError, match="llama-cpp-python not installed"):
            factory = LLMFactory()
            factory._initialize_local(mock_settings)


def test_initialize_local_load_failure() -> None:
    """Test failure when loading model fails."""
    mock_settings = MagicMock(spec=Settings)

    mock_llama_module = MagicMock()
    mock_llama_module.Llama.side_effect = Exception("Load failed")

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager:
            mock_manager.return_value.ensure_model_downloaded.return_value = "/path/to/model"
            factory = LLMFactory()
            client = factory._initialize_local(mock_settings)
            assert client is None
