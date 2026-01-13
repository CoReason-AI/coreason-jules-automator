from unittest.mock import MagicMock

import pytest

from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.utils.shell import CommandResult, ShellError


@pytest.fixture
def mock_shell() -> MagicMock:
    return MagicMock()


@pytest.fixture
def git(mock_shell: MagicMock) -> GitInterface:
    return GitInterface(shell_executor=mock_shell)


def test_has_changes_true(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test has_changes returns True when changes exist."""
    mock_shell.run.return_value = CommandResult(0, "M file.txt", "")
    assert git.has_changes() is True
    mock_shell.run.assert_called_with(["git", "status", "--porcelain"], check=True)


def test_has_changes_false(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test has_changes returns False when no changes exist."""
    mock_shell.run.return_value = CommandResult(0, "", "")
    assert git.has_changes() is False
    mock_shell.run.assert_called_with(["git", "status", "--porcelain"], check=True)


def test_has_changes_error(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test has_changes returns False on error."""
    mock_shell.run.side_effect = ShellError("Command failed", CommandResult(1, "", "error"))
    assert git.has_changes() is False


def test_push_to_branch_success(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test push_to_branch success when changes exist."""
    # Setup has_changes to return True (M file.txt)
    # The sequence of calls:
    # 1. rm -f .git/index.lock
    # 2. git add .
    # 3. git status --porcelain (inside has_changes)
    # 4. git commit
    # 5. git push

    # We need to configure side_effect or return_value carefully if the mock is reused
    # but here we can just ensure the return value for status call works.
    # Since run is called multiple times, we can use side_effect to return different values based on command?
    # Or simpler: just ensure that when called, it returns what we want.
    # The other commands don't use the return value (except for check=True which raises if needed, but we mock run).

    # Let's use side_effect to match commands if needed, but here a simple return value is okay
    # because only `has_changes` checks the output. Other commands output is ignored.
    mock_shell.run.return_value = CommandResult(0, "M file.txt", "")

    result = git.push_to_branch("feature/test", "commit message")

    assert result is True
    assert mock_shell.run.call_count == 5
    mock_shell.run.assert_any_call(["rm", "-f", ".git/index.lock"], check=False)
    mock_shell.run.assert_any_call(["git", "add", "."], check=True)
    mock_shell.run.assert_any_call(["git", "status", "--porcelain"], check=True)
    mock_shell.run.assert_any_call(["git", "commit", "-m", "commit message"], check=True)
    mock_shell.run.assert_any_call(["git", "push", "origin", "feature/test"], check=True)


def test_push_to_branch_no_changes(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test push_to_branch returns False when no changes detected."""
    # Setup has_changes to return False (empty stdout)
    mock_shell.run.return_value = CommandResult(0, "", "")

    result = git.push_to_branch("feature/test", "commit message")

    assert result is False
    # Calls: rm lock, add, status. (Commit and Push should NOT be called)
    assert mock_shell.run.call_count == 3
    mock_shell.run.assert_any_call(["rm", "-f", ".git/index.lock"], check=False)
    mock_shell.run.assert_any_call(["git", "add", "."], check=True)
    mock_shell.run.assert_any_call(["git", "status", "--porcelain"], check=True)

    # Ensure commit and push were NOT called
    for call in mock_shell.run.call_args_list:
        args = call[0][0]
        assert "commit" not in args
        assert "push" not in args


def test_push_to_branch_failure(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test push_to_branch failure."""
    # Simulate ShellError on rm or add
    mock_shell.run.side_effect = ShellError("Command failed", CommandResult(1, "", "error"))

    with pytest.raises(RuntimeError) as excinfo:
        git.push_to_branch("feature/test", "msg")

    assert "Git push failed" in str(excinfo.value)
