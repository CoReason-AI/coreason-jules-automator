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


def test_checkout_new_branch_success(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test checkout_new_branch success."""
    git.checkout_new_branch("new-branch", "base")
    mock_shell.run.assert_any_call(["git", "checkout", "base"], check=True)
    mock_shell.run.assert_any_call(["git", "pull", "origin", "base"], check=True)
    mock_shell.run.assert_any_call(["git", "checkout", "-b", "new-branch"], check=True)


def test_checkout_new_branch_failure(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test checkout_new_branch failure."""
    # Ensure checking out base fails to trigger first error path
    # But side_effect applies to ALL calls.
    mock_shell.run.side_effect = ShellError("error", CommandResult(1, "", "error"))
    with pytest.raises(RuntimeError) as excinfo:
        git.checkout_new_branch("new", "base")
    assert "Failed to checkout new branch" in str(excinfo.value)


def test_merge_squash_success(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test merge_squash success."""
    git.merge_squash("feature", "develop", "msg")
    mock_shell.run.assert_any_call(["git", "checkout", "develop"], check=True)
    mock_shell.run.assert_any_call(["git", "merge", "--squash", "feature"], check=True)
    mock_shell.run.assert_any_call(["git", "commit", "-m", "msg"], check=True)


def test_merge_squash_failure(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test merge_squash failure."""
    mock_shell.run.side_effect = ShellError("error", CommandResult(1, "", "error"))
    with pytest.raises(RuntimeError) as excinfo:
        git.merge_squash("feature", "develop", "msg")
    assert "Failed to squash merge" in str(excinfo.value)


def test_get_commit_log_success(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test get_commit_log success."""
    mock_shell.run.return_value = CommandResult(0, "feat: a\nfix: b", "")
    log = git.get_commit_log("base", "head")
    assert log == "feat: a\nfix: b"
    mock_shell.run.assert_called_with(["git", "log", "base..head", "--pretty=format:%s"], check=True)


def test_get_commit_log_failure(git: GitInterface, mock_shell: MagicMock) -> None:
    """Test get_commit_log failure."""
    mock_shell.run.side_effect = ShellError("error", CommandResult(1, "", "error"))
    with pytest.raises(RuntimeError) as excinfo:
        git.get_commit_log("base", "head")
    assert "Failed to get commit log" in str(excinfo.value)
