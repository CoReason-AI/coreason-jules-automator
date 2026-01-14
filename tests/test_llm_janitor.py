from unittest.mock import MagicMock

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


def test_janitor_summarize_logs_success() -> None:
    """Test summarize_logs with mocked LLM and PromptManager."""
    mock_client = MagicMock()
    mock_client.complete.return_value = "Summary"

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    summary = janitor.summarize_logs("long log...")

    assert summary == "Summary"
    # logs="long log..." is correct because "long log..." is much shorter than 2000 chars, so no slicing happens.
    mock_prompt_manager.render.assert_called_once_with("janitor_summarize.j2", logs="long log...")
    mock_client.complete.assert_called_once_with(
        messages=[{"role": "user", "content": "Rendered Prompt"}], max_tokens=150
    )


def test_janitor_summarize_logs_template_error() -> None:
    """Test handling of template rendering errors."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.side_effect = Exception("Template Error")

    janitor = JanitorService(llm_client=None, prompt_manager=mock_prompt_manager)
    summary = janitor.summarize_logs("log")

    assert summary == "Log summarization failed due to template error."


def test_janitor_summarize_logs_llm_error() -> None:
    """Test handling of LLM errors during summarization."""
    mock_client = MagicMock()
    mock_client.complete.side_effect = Exception("LLM Error")

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    summary = janitor.summarize_logs("log")

    assert summary == "Log summarization failed. Please check the logs directly."


def test_professionalize_commit_success() -> None:
    """Test professionalize_commit success."""
    mock_client = MagicMock()
    # Mock return value including JSON
    mock_client.complete.return_value = 'Sure! Here is the JSON:\n```json\n{"commit_text": "feat: new feature"}\n```'

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "feat: new feature"
    mock_prompt_manager.render.assert_called_with("janitor_professionalize.j2", commit_text="wip feature")


def test_professionalize_commit_retry_success() -> None:
    """Test professionalize_commit retries on invalid JSON."""
    mock_client = MagicMock()
    # First call: invalid JSON, Second call: valid JSON
    mock_client.complete.side_effect = ["Not JSON", '{"commit_text": "feat: retry success"}']

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "feat: retry success"
    assert mock_client.complete.call_count == 2


def test_professionalize_commit_failure() -> None:
    """Test professionalize_commit returns raw text after max retries."""
    mock_client = MagicMock()
    mock_client.complete.return_value = "Not JSON"

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Rendered Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "wip feature"
    assert mock_client.complete.call_count == 3


def test_professionalize_commit_prompt_error() -> None:
    """Test professionalize_commit handles prompt rendering error."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.side_effect = Exception("Prompt Error")

    janitor = JanitorService(llm_client=MagicMock(), prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "wip feature"


def test_professionalize_commit_no_client() -> None:
    """Test professionalize_commit handles missing client."""
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Prompt"

    janitor = JanitorService(llm_client=None, prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "wip feature"


def test_professionalize_commit_llm_exception() -> None:
    """Test professionalize_commit handles generic LLM exception."""
    mock_client = MagicMock()
    mock_client.complete.side_effect = Exception("LLM Error")

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.render.return_value = "Prompt"

    janitor = JanitorService(llm_client=mock_client, prompt_manager=mock_prompt_manager)
    result = janitor.professionalize_commit("wip feature")

    assert result == "wip feature"
    # Should stop after first exception, not retry loop for generic exceptions?
    # The code breaks on generic exception:
    # except Exception as e:
    #    logger.error(f"LLM generation failed: {e}")
    #    break
    assert mock_client.complete.call_count == 1
