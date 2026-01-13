from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from coreason_jules_automator.strategies.remote import RemoteDefenseStrategy
from coreason_jules_automator.strategies.base import DefenseResult

@pytest.fixture
def remote_strategy():
    github = MagicMock()
    janitor = MagicMock()
    git = MagicMock()

    github.get_pr_checks = AsyncMock(return_value=[{"status": "completed", "conclusion": "success"}])
    janitor.sanitize_commit = MagicMock(return_value="sanitized")
    git.push_to_branch = AsyncMock()
    janitor.summarize_logs = AsyncMock(return_value="summary")

    return RemoteDefenseStrategy(github, janitor, git)

@pytest.mark.asyncio
async def test_execute_success(remote_strategy):
    context = {"branch_name": "test"}
    result = await remote_strategy.execute(context)
    assert result.success
    remote_strategy.git.push_to_branch.assert_called_once()
    remote_strategy.github.get_pr_checks.assert_called()

@pytest.mark.asyncio
async def test_execute_failure_push(remote_strategy):
    remote_strategy.git.push_to_branch.side_effect = RuntimeError("Push failed")
    context = {"branch_name": "test"}
    result = await remote_strategy.execute(context)
    assert not result.success
    assert "Push failed" in result.message

@pytest.mark.asyncio
async def test_execute_failure_ci_checks(remote_strategy):
    # Simulate CI failure
    remote_strategy.github.get_pr_checks.return_value = [
        {"status": "completed", "conclusion": "failure", "name": "test-check", "url": "http://log"}
    ]
    context = {"branch_name": "test"}
    result = await remote_strategy.execute(context)
    assert not result.success
    assert "summary" in result.message
    remote_strategy.janitor.summarize_logs.assert_called_once()

@pytest.mark.asyncio
async def test_execute_timeout(remote_strategy):
    # Simulate pending checks forever
    remote_strategy.github.get_pr_checks.return_value = [
        {"status": "in_progress", "conclusion": None}
    ]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        context = {"branch_name": "test"}
        result = await remote_strategy.execute(context)
        assert not result.success
        assert "Line 2 timeout" in result.message
        assert mock_sleep.call_count >= 10

@pytest.mark.asyncio
async def test_execute_poll_exception(remote_strategy):
    # Simulate exception during polling
    remote_strategy.github.get_pr_checks.side_effect = RuntimeError("API Error")

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        context = {"branch_name": "test"}
        result = await remote_strategy.execute(context)
        assert not result.success
        assert "Line 2 timeout" in result.message # It should exhaust retries
        assert mock_sleep.call_count >= 10
