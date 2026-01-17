from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface, AsyncGitInterface
from coreason_jules_automator.async_api.strategies import AsyncLocalDefenseStrategy, AsyncRemoteDefenseStrategy
from coreason_jules_automator.config import Settings
from coreason_jules_automator.domain.context import OrchestrationContext
from coreason_jules_automator.domain.scm import PullRequestStatus
from coreason_jules_automator.llm.janitor import JanitorService

# --- AsyncLocalDefenseStrategy Tests ---


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        repo_name="dummy/repo",
        GITHUB_TOKEN="dummy_token",
        GOOGLE_API_KEY="dummy_key",
        max_retries=5,
        extensions_enabled=["security", "code-review"],
    )


@pytest.mark.asyncio
async def test_local_strategy_success(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock()
    mock_gemini.code_review = AsyncMock()

    strategy = AsyncLocalDefenseStrategy(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await strategy.execute(context)

    assert result.success is True
    mock_gemini.security_scan.assert_awaited_once()
    mock_gemini.code_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_local_strategy_security_fail(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock(side_effect=RuntimeError("Sec Fail"))

    mock_settings.extensions_enabled = ["security"]
    strategy = AsyncLocalDefenseStrategy(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await strategy.execute(context)

    assert result.success is False
    assert "Security Scan failed" in result.message


@pytest.mark.asyncio
async def test_local_strategy_code_review_fail(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock(side_effect=RuntimeError("Lint Fail"))

    mock_settings.extensions_enabled = ["code-review"]
    strategy = AsyncLocalDefenseStrategy(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await strategy.execute(context)

    assert result.success is False
    assert "Code Review failed" in result.message


# --- AsyncRemoteDefenseStrategy Tests ---


@pytest.fixture
def remote_deps(mock_settings: Settings) -> Dict[str, Any]:
    return {
        "settings": mock_settings,
        "github": MagicMock(spec=AsyncGitHubInterface),
        "git": MagicMock(spec=AsyncGitInterface),
        "janitor": MagicMock(spec=JanitorService),
        "llm_client": MagicMock(spec=AsyncLLMClient),
    }


# Removed test_remote_strategy_missing_context because Pydantic model ensures fields are present.


@pytest.mark.asyncio
async def test_remote_strategy_push_fail(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(side_effect=RuntimeError("Push error"))
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")
    result = await strategy.execute(context)
    assert result.success is False
    assert "Failed to push code" in result.message


@pytest.mark.asyncio
async def test_remote_strategy_no_changes(remote_deps: Dict[str, MagicMock]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=False)
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")
    result = await strategy.execute(context)
    assert result.success is True
    assert "No changes detected" in result.message


@pytest.mark.asyncio
async def test_remote_strategy_poll_success(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="completed", conclusion="success", url="http://url")]
    )

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(context)
        assert result.success is True


@pytest.mark.asyncio
async def test_remote_strategy_poll_empty_checks(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # First empty, then success
    remote_deps["github"].get_pr_checks = AsyncMock(
        side_effect=[[], [PullRequestStatus(name="check1", status="completed", conclusion="success", url="http://url")]]
    )

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(context)
        assert result.success is True


@pytest.mark.asyncio
async def test_remote_strategy_poll_error(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # Error then success
    remote_deps["github"].get_pr_checks = AsyncMock(
        side_effect=[
            RuntimeError("API Error"),
            [PullRequestStatus(name="check1", status="completed", conclusion="success", url="http://url")],
        ]
    )

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(context)
        assert result.success is True


@pytest.mark.asyncio
async def test_remote_strategy_poll_timeout(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # Always pending
    remote_deps["github"].get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="in_progress", conclusion=None, url="http://url")]
    )

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Should loop max_poll_attempts times
        result = await strategy.execute(context)
        assert result.success is False
        assert "timeout" in result.message


@pytest.mark.asyncio
async def test_remote_strategy_ci_failure_no_llm(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="test", status="completed", conclusion="failure", url="http://url")]
    )
    # Explicitly set llm_client to None for this test, bypassing type check for the mock dict
    deps: Dict[str, Any] = remote_deps.copy()
    deps["llm_client"] = None

    strategy = AsyncRemoteDefenseStrategy(**deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(context)
        assert result.success is False
        assert "CI checks failed" in result.message


@pytest.mark.asyncio
async def test_remote_strategy_long_log_truncation(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="test", status="completed", conclusion="failure", url="http://url")]
    )

    # Very long log (streamed)
    # We yield more than 2000 lines to trigger truncation
    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        for i in range(2500):
            yield f"Line {i}"

    remote_deps["github"].get_latest_run_log = mock_stream

    mock_llm_response = MagicMock(content="Summary")
    remote_deps["llm_client"].execute = AsyncMock(return_value=mock_llm_response)

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await strategy.execute(context)

    # Check that janitor was called with truncated log
    # The log snippet will contain the end of the log
    call_args = remote_deps["janitor"].build_summarize_request.call_args
    assert call_args is not None
    snippet = call_args[0][0]

    # Verify we have the tail
    assert "Line 2499" in snippet
    # Verify we lost the head
    assert "Line 0" not in snippet
    assert "--- Logs ---" in snippet


@pytest.mark.asyncio
async def test_remote_strategy_janitor_exception(remote_deps: Dict[str, Any]) -> None:
    # Test line 266: logger.error(f"Janitor summarization failed: {e}")
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    remote_deps["github"].get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="test", status="completed", conclusion="failure", url="http://url")]
    )

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "log"

    remote_deps["github"].get_latest_run_log = mock_stream

    # LLM raises exception
    remote_deps["llm_client"].execute = AsyncMock(side_effect=Exception("LLM Fail"))

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await strategy.execute(context)

    assert result.success is False
    assert "Log summarization failed" in result.message


@pytest.mark.asyncio
async def test_remote_strategy_handle_ci_failure_fallback(remote_deps: Dict[str, MagicMock]) -> None:
    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    # Call private method directly to hit the fallback return
    msg = await strategy._handle_ci_failure([], "branch")
    assert "could not identify specific check failure" in msg


@pytest.mark.asyncio
async def test_remote_strategy_poll_exception(remote_deps: Dict[str, Any]) -> None:
    remote_deps["git"].push_to_branch = AsyncMock(return_value=True)
    # Raise RuntimeError during polling to trigger the exception handler
    # We ensure get_pr_checks raises ONLY when awaited
    remote_deps["github"].get_pr_checks = AsyncMock(side_effect=RuntimeError("Polling Error"))

    strategy = AsyncRemoteDefenseStrategy(**remote_deps)
    context = OrchestrationContext(task_id="t1", branch_name="feat", session_id="123")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("coreason_jules_automator.async_api.strategies.logger.warning") as mock_log:
            # It will retry until max attempts, so we just check if it fails gracefully
            result = await strategy.execute(context)

            assert result.success is False
            assert "timeout" in result.message
            # Verify the exception was logged, ensuring coverage of line 216
            mock_log.assert_called()
            # Check that at least one call contains our expected error
            found_error = any("Poll attempt failed: Polling Error" in str(call) for call in mock_log.call_args_list)
            assert found_error, "Expected log message not found"
