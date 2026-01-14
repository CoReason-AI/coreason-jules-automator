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


def test_janitor_parse_professionalize_response_success() -> None:
    """Test parse_professionalize_response with valid JSON."""
    janitor = JanitorService()
    llm_response = 'Sure! Here is the JSON:\n```json\n{"commit_text": "feat: new feature"}\n```'
    result = janitor.parse_professionalize_response("original", llm_response)
    assert result == "feat: new feature"


def test_janitor_parse_professionalize_response_invalid_json() -> None:
    """Test parse_professionalize_response with invalid JSON returns fallback."""
    janitor = JanitorService()
    llm_response = "Not JSON"
    # Fallback should be sanitized original
    original = "original\nCo-authored-by: bot"
    result = janitor.parse_professionalize_response(original, llm_response)
    assert result == "original"


def test_janitor_parse_professionalize_response_no_braces() -> None:
    """Test parse_professionalize_response with no braces returns fallback."""
    janitor = JanitorService()
    llm_response = "Just some text"
    result = janitor.parse_professionalize_response("original", llm_response)
    assert result == "original"

def test_janitor_parse_professionalize_response_incomplete_json() -> None:
    """Test parse_professionalize_response with malformed JSON returns fallback."""
    janitor = JanitorService()
    llm_response = '{"commit_text": "incomplete'
    result = janitor.parse_professionalize_response("original", llm_response)
    assert result == "original"

def test_janitor_parse_professionalize_response_json_decode_error() -> None:
    """Test parse_professionalize_response catches JSONDecodeError."""
    janitor = JanitorService()
    # Has braces, but invalid JSON content
    llm_response = "{ invalid json }"
    result = janitor.parse_professionalize_response("original", llm_response)
    assert result == "original"
