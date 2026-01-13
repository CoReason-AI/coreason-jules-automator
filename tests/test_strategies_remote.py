from unittest.mock import MagicMock, patch

import pytest
from coreason_jules_automator.strategies.remote import RemoteDefenseStrategy


@pytest.fixture
def mock_github() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_janitor() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_git() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_emitter() -> MagicMock:
    return MagicMock()


@pytest.fixture
def strategy(
    mock_github: MagicMock, mock_janitor: MagicMock, mock_git: MagicMock, mock_emitter: MagicMock
) -> RemoteDefenseStrategy:
    return RemoteDefenseStrategy(github=mock_github, janitor=mock_janitor, git=mock_git, event_emitter=mock_emitter)


def test_execute_missing_branch(strategy: RemoteDefenseStrategy) -> None:
    """Test execution without branch name."""
    result = strategy.execute({})
    assert result.success is False
    assert "Missing branch_name" in result.message


def test_execute_push_failure(
    strategy: RemoteDefenseStrategy, mock_github: MagicMock, mock_janitor: MagicMock, mock_git: MagicMock
) -> None:
    """Test execution when push fails."""
    mock_janitor.sanitize_commit.return_value = "clean commit"
    mock_git.push_to_branch.side_effect = RuntimeError("Push failed")

    result = strategy.execute({"branch_name": "feature/test"})

    assert result.success is False
    assert "Failed to push code: Push failed" in result.message


def test_execute_success(
    strategy: RemoteDefenseStrategy,
    mock_github: MagicMock,
    mock_janitor: MagicMock,
    mock_git: MagicMock,
    mock_emitter: MagicMock,
) -> None:
    """Test successful execution."""
    mock_janitor.sanitize_commit.return_value = "clean commit"
    # Return empty list first (wait), then success
    mock_github.get_pr_checks.side_effect = [
        [],
        [{"name": "test", "status": "completed", "conclusion": "success"}],
    ]

    # We need to speed up time.sleep
    with patch("time.sleep"):
        result = strategy.execute({"branch_name": "feature/test"})

    assert result.success is True
    assert result.message == "CI checks passed"
    assert mock_github.get_pr_checks.call_count == 2

    # Check for waiting events
    calls = [args[0] for args, _ in mock_emitter.emit.call_args_list]
    waiting_events = [e for e in calls if "Waiting for checks..." in e.message]
    assert len(waiting_events) >= 2


def test_execute_check_failure(
    strategy: RemoteDefenseStrategy, mock_github: MagicMock, mock_janitor: MagicMock
) -> None:
    """Test execution when a check fails."""
    mock_janitor.sanitize_commit.return_value = "clean commit"
    mock_github.get_pr_checks.return_value = [
        {"name": "test", "status": "completed", "conclusion": "failure", "url": "http://logs"}
    ]
    mock_janitor.summarize_logs.return_value = "Logs suggest failure X"

    with patch("time.sleep"):
        result = strategy.execute({"branch_name": "feature/test"})

    assert result.success is False
    assert result.message == "Logs suggest failure X"
    mock_janitor.summarize_logs.assert_called_once()


def test_execute_timeout(strategy: RemoteDefenseStrategy, mock_github: MagicMock, mock_janitor: MagicMock) -> None:
    """Test execution when checks time out (never complete)."""
    mock_janitor.sanitize_commit.return_value = "clean commit"
    mock_github.get_pr_checks.return_value = [{"name": "test", "status": "in_progress"}]

    with patch("time.sleep"):
        result = strategy.execute({"branch_name": "feature/test"})

    assert result.success is False
    assert "timeout" in result.message.lower()
    assert mock_github.get_pr_checks.call_count == 10  # max attempts


def test_execute_poll_exception(
    strategy: RemoteDefenseStrategy, mock_github: MagicMock, mock_janitor: MagicMock
) -> None:
    """Test execution when polling raises exceptions repeatedly."""
    mock_janitor.sanitize_commit.return_value = "clean commit"
    mock_github.get_pr_checks.side_effect = RuntimeError("API Error")

    with patch("time.sleep"):
        result = strategy.execute({"branch_name": "feature/test"})

    assert result.success is False
    assert "timeout" in result.message.lower()


def test_handle_ci_failure_fallback(strategy: RemoteDefenseStrategy) -> None:
    """Test fallback message when no specific failure is found."""
    # Pass a check that is successful, so next(...) returns None
    checks = [{"name": "test", "status": "completed", "conclusion": "success"}]
    summary = strategy._handle_ci_failure(checks)
    assert summary == "CI checks failed but could not identify specific check failure."
