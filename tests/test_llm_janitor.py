from unittest.mock import MagicMock

import pytest

from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.llm.types import LLMRequest


def test_janitor_initialization() -> None:
    """Test JanitorService initializes with default prompt manager."""
    service = JanitorService()
    assert isinstance(service.prompt_manager, PromptManager)


def test_janitor_sanitize_commit() -> None:
    """Test commit message sanitization."""
    janitor = JanitorService()
    raw = "feat: add feature\n\nCo-authored-by: bot\nSigned-off-by: me"
    clean = janitor.sanitize_commit(raw)
    assert clean == "feat: add feature"


def test_janitor_build_summarize_request() -> None:
    """Test build_summarize_request returns correct LLMRequest."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(prompt_manager=mock_prompt_manager)
    request = janitor.build_summarize_request("long log...")

    assert isinstance(request, LLMRequest)
    assert request.messages == [{"role": "user", "content": "Rendered Prompt"}]
    assert request.max_tokens == 150
    mock_prompt_manager.render.assert_called_once_with("janitor_summarize.j2", logs="long log...")


def test_janitor_build_summarize_request_template_error() -> None:
    """Test build_summarize_request raises error on template failure."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.side_effect = Exception("Template Error")

    janitor = JanitorService(prompt_manager=mock_prompt_manager)

    with pytest.raises(Exception, match="Template Error"):
        janitor.build_summarize_request("log")


def test_janitor_build_professionalize_request() -> None:
    """Test build_professionalize_request returns correct LLMRequest."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Professionalize Prompt"

    janitor = JanitorService(prompt_manager=mock_prompt_manager)

    # Check simple case
    request = janitor.build_professionalize_request("simple feature")
    assert isinstance(request, LLMRequest)
    assert request.messages == [{"role": "user", "content": "Professionalize Prompt"}]
    assert request.max_tokens == 200

    # Check sanitization
    raw = "wip feature\nCo-authored-by: bot"
    janitor.build_professionalize_request(raw)
    mock_prompt_manager.render.assert_called_with("janitor_professionalize.j2", commit_text="wip feature")
