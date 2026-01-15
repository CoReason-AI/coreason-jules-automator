import asyncio
import pytest
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from coreason_jules_automator.async_api.strategies import AsyncLocalDefenseStrategy, AsyncRemoteDefenseStrategy, AsyncDefenseStrategy
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitInterface, AsyncGitHubInterface
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.strategies.base import DefenseResult
from coreason_jules_automator.events import EventEmitter

# --- AsyncLocalDefenseStrategy Tests ---

@pytest.mark.asyncio
async def test_local_strategy_success() -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock()
    mock_gemini.code_review = AsyncMock()

    strategy = AsyncLocalDefenseStrategy(gemini=mock_gemini)

    with patch("coreason_jules_automator.async_api.strategies.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]
        result = await strategy.execute({})

        assert result.success is True
        mock_gemini.security_scan.assert_awaited_once()
        mock_gemini.code_review.assert_awaited_once()

@pytest.mark.asyncio
async def test_local_strategy_security_fail() -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock(side_effect=RuntimeError("Sec Fail"))

    strategy = AsyncLocalDefenseStrategy(gemini=mock_gemini)

    with patch("coreason_jules_automator.async_api.strategies.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security"]
        result = await strategy.execute({})

        assert result.success is False
        assert "Security Scan failed" in result.message

@pytest.mark.asyncio
async def test_local_strategy_code_review_fail() -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock(side_effect=RuntimeError("Lint Fail"))

    strategy = AsyncLocalDefenseStrategy(gemini=mock_gemini)

    with patch("coreason_jules_automator.async_api.strategies.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["code-review"]
        result = await strategy.execute({})

        assert result.success is False
        assert "Code Review failed" in result.message

# --- AsyncRemoteDefenseStrategy Tests ---

@pytest.fixture
def remote_deps() -> Dict[str, MagicMock]:
    return {
        "github": MagicMock(spec=AsyncGitHubInterface),
        "git": MagicMock(spec=AsyncGitInterface),
        "janitor": MagicMock(spec=JanitorService),
        "llm_client": MagicMock(spec=AsyncLLMClient),
    }

@pytest.mark.asyncio
async def test_remote_strategy_missing_context(remote_deps: Dict[str, MagicMock]) -> None:
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    result = await strategy.execute({})
    assert result.success is False
    assert "Missing branch_name" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_push_fail(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(side_effect=RuntimeError("Push error"))
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    result = await strategy.execute({"branch_name": "feat", "sid": "123"})
    assert result.success is False
    assert "Failed to push code" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_no_changes(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=False)
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    result = await strategy.execute({"branch_name": "feat", "sid": "123"})
    assert result.success is True
    assert "No changes detected" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_poll_success(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "completed", "conclusion": "success"}
    ])

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is True

@pytest.mark.asyncio
async def test_remote_strategy_poll_empty_checks(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # First empty, then success
    remote_deps["github"].get_pr_checks = AsyncMock(side_effect=[
        [],
        [{"status": "completed", "conclusion": "success"}]
    ])

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is True

@pytest.mark.asyncio
async def test_remote_strategy_poll_error(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # Error then success
    remote_deps["github"].get_pr_checks = AsyncMock(side_effect=[
        RuntimeError("API Error"),
        [{"status": "completed", "conclusion": "success"}]
    ])

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is True

@pytest.mark.asyncio
async def test_remote_strategy_poll_timeout(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # Always pending
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "in_progress", "conclusion": None}
    ])

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Should loop max_poll_attempts times
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is False
        assert "timeout" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_ci_failure_no_llm(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "completed", "conclusion": "failure", "name": "test"}
    ])
    # Explicitly set llm_client to None for this test, bypassing type check for the mock dict
    deps: Dict[str, Any] = remote_deps.copy()
    deps["llm_client"] = None

    strategy = AsyncRemoteDefenseStrategy(**deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is False
        assert "CI checks failed" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_ci_failure_llm_error(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "completed", "conclusion": "failure", "name": "test"}
    ])
    remote_deps["github"].get_latest_run_log = AsyncMock(return_value="log")

    remote_deps["llm_client"].execute = AsyncMock(side_effect=Exception("LLM Fail"))

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})
        assert result.success is False
        assert "Log summarization failed" in result.message

@pytest.mark.asyncio
async def test_remote_strategy_ci_failure_analysis(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "completed", "conclusion": "failure", "name": "test", "url": "http://log"}
    ])
    remote_deps["github"].get_latest_run_log = AsyncMock(return_value="Detailed Error Log")

    mock_llm_resp = MagicMock()
    mock_llm_resp.content = "Summary: Test failed"
    remote_deps["llm_client"].execute = AsyncMock(return_value=mock_llm_resp)

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})

        assert result.success is False
        assert "Summary: Test failed" in result.message
        # Verify log fetching was called
        remote_deps["github"].get_latest_run_log.assert_awaited_with("feat")

@pytest.mark.asyncio
async def test_remote_strategy_handle_ci_failure_no_failed_check(remote_deps: Dict[str, MagicMock]) -> None:
    # Direct test for dead code path where conclusion != success but logic misses it?
    # Or just empty list passed to _handle_ci_failure
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    # This shouldn't happen in real exec flow but covers the "if failed_check" branch
    msg = await strategy._handle_ci_failure([], "branch")
    assert "could not identify specific check failure" in msg

@pytest.mark.asyncio
async def test_remote_strategy_janitor_exception(remote_deps: Dict[str, MagicMock]) -> None:
    # Force janitor to raise an exception to cover line 266
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(return_value=[
        {"status": "completed", "conclusion": "failure", "name": "test", "url": "http://log"}
    ])
    remote_deps["github"].get_latest_run_log = AsyncMock(return_value="log")

    remote_deps["janitor"].build_summarize_request.side_effect = Exception("Janitor Error")

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute({"branch_name": "feat", "sid": "123"})

        assert result.success is False
        assert "Log summarization failed" in result.message
