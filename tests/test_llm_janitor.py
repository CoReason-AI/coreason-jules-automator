from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager


def test_janitor_initialization() -> None:
    """Test JanitorService initializes with default prompt manager."""
    service = JanitorService(llm_client=None)
    assert isinstance(service.prompt_manager, PromptManager)


def test_janitor_sanitize_commit() -> None:
    """Test commit message sanitization."""
    janitor = JanitorService(llm_client=None)
    raw = "feat: add feature\n\nCo-authored-by: bot\nSigned-off-by: me"
    clean = janitor.sanitize_commit(raw)
    assert clean == "feat: add feature"


@pytest.mark.asyncio
async def test_janitor_summarize_logs_success() -> None:
    """Test summarize_logs with mocked LLM and PromptManager."""
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(return_value="Summary")

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    summary = await janitor.summarize_logs("long log...")

    assert summary == "Summary"
    # logs="long log..." is correct because "long log..." is much shorter than 2000 chars, so no slicing happens.
    mock_prompt_manager.render.assert_called_once_with("janitor_summarize.j2", logs="long log...")
    mock_client.complete.assert_called_once_with(
        messages=[{"role": "user", "content": "Rendered Prompt"}], max_tokens=150
    )


@pytest.mark.asyncio
async def test_janitor_summarize_logs_template_error() -> None:
    """Test handling of template rendering errors."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.side_effect = Exception("Template Error")

    janitor = JanitorService(llm_client=None, prompt_manager=mock_prompt_manager)
    summary = await janitor.summarize_logs("log")

    assert summary == "Log summarization failed due to template error."
