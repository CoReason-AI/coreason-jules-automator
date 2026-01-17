import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.llm.factory import LLMFactory
from coreason_jules_automator.llm.janitor import CommitMessageResponse, JanitorService, SummaryResponse
from coreason_jules_automator.llm.model_manager import ModelManager


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COREASON_GITHUB_TOKEN", "dummy")
    monkeypatch.setenv("COREASON_GOOGLE_API_KEY", "dummy")
    monkeypatch.setenv("COREASON_REPO_NAME", "dummy/repo")
    monkeypatch.setenv("COREASON_LLM_STRATEGY", "api")
    get_settings.cache_clear()


def test_factory_get_client_api_openai(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory returns OpenAI client when configured."""
    monkeypatch.setenv("COREASON_OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    settings = get_settings()

    mock_openai_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        client = LLMFactory().get_client(settings)
        mock_openai_module.OpenAI.assert_called_once()
        assert client is not None


def test_factory_get_client_api_deepseek(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test factory returns OpenAI client configured for DeepSeek."""
    monkeypatch.delenv("COREASON_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("COREASON_DEEPSEEK_API_KEY", "sk-deepseek")
    get_settings.cache_clear()
    settings = get_settings()

    mock_openai_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        client = LLMFactory().get_client(settings)
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["api_key"] == "sk-deepseek"
        assert call_kwargs["base_url"] == "https://api.deepseek.com"
        assert client is not None


def test_factory_local_fallback(mock_settings: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fallback to local if API key missing."""
    monkeypatch.delenv("COREASON_OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    settings = get_settings()

    mock_llama_module = MagicMock()
    with patch.dict(sys.modules, {"llama_cpp": mock_llama_module}):
        with patch("coreason_jules_automator.llm.model_manager.hf_hub_download", return_value="/tmp/model.gguf"):
            client = LLMFactory().get_client(settings)
            mock_llama_module.Llama.assert_called_once()
            assert client is not None


def test_model_manager_download_success() -> None:
    """Test successful model download."""
    with patch("coreason_jules_automator.llm.model_manager.hf_hub_download", return_value="/path/to/model") as mock_dl:
        manager = ModelManager()
        path = manager.ensure_model_downloaded()
        assert path == "/path/to/model"
        mock_dl.assert_called_once()


def test_model_manager_download_failure() -> None:
    """Test failed model download."""
    with patch("coreason_jules_automator.llm.model_manager.hf_hub_download", side_effect=Exception("Net error")):
        manager = ModelManager()
        with pytest.raises(RuntimeError) as excinfo:
            manager.ensure_model_downloaded()
        assert "Failed to download model" in str(excinfo.value)


@pytest.mark.asyncio
async def test_janitor_professionalize_commit() -> None:
    """Test commit message professionalization."""
    mock_llm = AsyncMock(spec=AsyncLLMClient)
    mock_llm.execute.return_value = CommitMessageResponse(commit_text="feat: add feature")

    janitor = JanitorService(llm_client=mock_llm)
    raw = "feat: add feature\n\nCo-authored-by: bot\nSigned-off-by: me"

    # We test the method, not internal sanitization (since that's now implicit or handled by LLM)
    # The prompt should contain the raw text.
    result = await janitor.professionalize_commit(raw)
    assert result == "feat: add feature"

    args, _ = mock_llm.execute.call_args
    request = args[0]
    assert raw in request.messages[0]["content"]


@pytest.mark.asyncio
async def test_janitor_summarize_logs() -> None:
    """Test log summarization."""
    mock_llm = AsyncMock(spec=AsyncLLMClient)
    mock_llm.execute.return_value = SummaryResponse(summary="Summary")

    janitor = JanitorService(llm_client=mock_llm)

    result = await janitor.summarize_logs("log data")
    assert result == "Summary"

    args, _ = mock_llm.execute.call_args
    request = args[0]
    assert "log data" in request.messages[0]["content"]
