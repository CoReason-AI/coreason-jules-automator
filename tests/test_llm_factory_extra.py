from unittest.mock import MagicMock, patch
import pytest
from coreason_jules_automator.config import Settings
from coreason_jules_automator.llm.factory import LLMFactory

def test_get_client_openai_import_error() -> None:
    """Test get_client falls back to local when openai is not installed."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"

    with patch.dict("sys.modules", {"openai": None}):
        factory = LLMFactory()
        # Mock _initialize_local to avoid actual local initialization logic and return a dummy
        with patch.object(factory, "_initialize_local") as mock_init_local:
            mock_init_local.return_value = "local_client"
            client = factory.get_client(mock_settings)

            assert client == "local_client"
            mock_init_local.assert_called_once_with(mock_settings)

def test_initialize_local_llama_import_error() -> None:
    """Test _initialize_local raises RuntimeError when llama_cpp is not installed."""
    mock_settings = MagicMock(spec=Settings)

    with patch.dict("sys.modules", {"llama_cpp": None}):
        factory = LLMFactory()
        with pytest.raises(RuntimeError, match="llama-cpp-python not installed"):
            factory._initialize_local(mock_settings)

def test_initialize_local_download_error() -> None:
    """Test _initialize_local returns None when model download fails."""
    mock_settings = MagicMock(spec=Settings)

    with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager_cls:
        # We need to simulate successful import of llama_cpp
        with patch.dict("sys.modules", {"llama_cpp": MagicMock()}):
            mock_manager = mock_manager_cls.return_value
            mock_manager.ensure_model_downloaded.side_effect = RuntimeError("Download failed")

            factory = LLMFactory()
            client = factory._initialize_local(mock_settings)

            assert client is None

def test_initialize_local_general_exception() -> None:
    """Test _initialize_local returns None on generic exception during loading."""
    mock_settings = MagicMock(spec=Settings)

    with patch("coreason_jules_automator.llm.factory.ModelManager") as mock_manager_cls:
         with patch.dict("sys.modules", {"llama_cpp": MagicMock()}):
            mock_manager = mock_manager_cls.return_value
            mock_manager.ensure_model_downloaded.return_value = "/path/to/model"

            # Mock Llama constructor to raise Exception
            with patch("llama_cpp.Llama", side_effect=Exception("Load failed")):
                factory = LLMFactory()
                client = factory._initialize_local(mock_settings)

                assert client is None
