from unittest.mock import AsyncMock, MagicMock

import pytest

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.llm.janitor import JanitorService, CommitMessageResponse, SummaryResponse
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.llm.types import LLMRequest


def test_janitor_initialization() -> None:
    """Test JanitorService initializes with default prompt manager."""
    service = JanitorService()
    assert isinstance(service.prompt_manager, PromptManager)
    assert service.llm_client is None


@pytest.mark.asyncio
async def test_professionalize_commit_no_client() -> None:
    janitor = JanitorService()
    raw = "test commit"
    result = await janitor.professionalize_commit(raw)
    assert result == "test commit"


@pytest.mark.asyncio
async def test_professionalize_commit_with_client() -> None:
    mock_client = AsyncMock(spec=AsyncLLMClient)
    mock_client.execute.return_value = CommitMessageResponse(commit_text="Professional commit")

    janitor = JanitorService(llm_client=mock_client)
    raw = "bad commit"
    result = await janitor.professionalize_commit(raw)

    assert result == "Professional commit"
    mock_client.execute.assert_called_once()

    # Verify request content roughly
    call_args = mock_client.execute.call_args
    request = call_args[0][0]
    assert isinstance(request, LLMRequest)
    assert "bad commit" in request.messages[0]["content"]


@pytest.mark.asyncio
async def test_summarize_logs_no_client() -> None:
    janitor = JanitorService()
    logs = "error logs"
    result = await janitor.summarize_logs(logs)
    assert "unavailable" in result


@pytest.mark.asyncio
async def test_summarize_logs_with_client() -> None:
    mock_client = AsyncMock(spec=AsyncLLMClient)
    mock_client.execute.return_value = SummaryResponse(summary="Short summary")

    janitor = JanitorService(llm_client=mock_client)
    logs = "long logs"
    result = await janitor.summarize_logs(logs)

    assert result == "Short summary"
    mock_client.execute.assert_called_once()
