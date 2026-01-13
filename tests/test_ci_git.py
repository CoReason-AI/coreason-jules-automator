from unittest.mock import MagicMock

import pytest
from coreason_jules_automator.ci.git import GitInterface


@pytest.fixture
def git() -> GitInterface:
    return GitInterface()


def test_push_to_branch_success() -> None:
    """Test push_to_branch success."""
    mock_shell = MagicMock()
    git = GitInterface(shell_executor=mock_shell)

    git.push_to_branch("feature/test", "commit message")

    assert mock_shell.run.call_count == 3
    mock_shell.run.assert_any_call(["git", "add", "."], check=True)
    mock_shell.run.assert_any_call(["git", "commit", "-m", "commit message"], check=True)
    mock_shell.run.assert_any_call(["git", "push", "origin", "feature/test"], check=True)


def test_push_to_branch_failure(git: GitInterface) -> None:
    """Test push_to_branch failure."""
    mock_shell = MagicMock()
    git = GitInterface(shell_executor=mock_shell)

    # Simulate ShellError
    from coreason_jules_automator.utils.shell import CommandResult, ShellError

    result = CommandResult(1, "", "error")
    mock_shell.run.side_effect = ShellError("Command failed", result)

    with pytest.raises(RuntimeError) as excinfo:
        git.push_to_branch("feature/test", "msg")

    assert "Git push failed" in str(excinfo.value)
