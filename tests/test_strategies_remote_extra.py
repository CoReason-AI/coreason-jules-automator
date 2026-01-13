from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coreason_jules_automator.strategies.remote import RemoteDefenseStrategy
from coreason_jules_automator.utils.logger import logger


@pytest.fixture
def remote_strategy() -> RemoteDefenseStrategy:
    github = MagicMock()
    janitor = MagicMock()
    git = MagicMock()

    github.get_pr_checks = AsyncMock(return_value=[{"status": "completed", "conclusion": "success"}])
    janitor.sanitize_commit = MagicMock(return_value="sanitized")
    git.push_to_branch = AsyncMock()
    janitor.summarize_logs = AsyncMock(return_value="summary")

    return RemoteDefenseStrategy(github, janitor, git)


@pytest.mark.asyncio
async def test_execute_missing_branch_name(remote_strategy: Any) -> None:
    """Test execute with missing branch name."""
    context: Dict[str, Any] = {}  # Missing branch_name
    result = await remote_strategy.execute(context)
    assert not result.success
    assert "Missing branch_name" in result.message


@pytest.mark.asyncio
async def test_execute_poll_runtime_error(remote_strategy: Any) -> None:
    """Test execute polling loop handles RuntimeError from get_pr_checks."""
    remote_strategy.github.get_pr_checks.side_effect = RuntimeError("API failure")

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        context = {"branch_name": "test"}

        # Spy on logger
        with patch.object(logger, "warning") as mock_logger_warning:
            # It will retry max_poll_attempts times then fail
            result = await remote_strategy.execute(context)

            assert not result.success
            assert "Line 2 timeout" in result.message
            assert mock_sleep.call_count >= 10

            # Verify exception was logged
            assert mock_logger_warning.call_count >= 10
            mock_logger_warning.assert_any_call("Failed to poll checks: API failure")


@pytest.mark.asyncio
async def test_handle_ci_failure_no_failed_check(remote_strategy: Any) -> None:
    """Test _handle_ci_failure when no check has explicitly failed (fallback)."""
    # This scenario is theoretically reachable if logic drifts, but testing the helper directly ensures coverage.
    checks = [{"conclusion": "success", "status": "completed"}]  # No failure here

    # However, _handle_ci_failure is called when there IS a failure.
    # So we should pass checks where conclusion != success is NOT present,
    # to see if it returns the fallback message.

    summary = await remote_strategy._handle_ci_failure(checks)
    assert summary == "CI checks failed but could not identify specific check failure."
