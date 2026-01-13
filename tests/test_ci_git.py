from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.utils.shell import CommandResult, ShellError


@pytest.fixture
def git() -> GitInterface:
    return GitInterface()


@pytest.mark.asyncio
async def test_push_to_branch_success() -> None:
    """Test push_to_branch success."""
    mock_shell = MagicMock()
    mock_shell.run_async = AsyncMock(return_value=CommandResult(0, "", ""))
    git = GitInterface(shell_executor=mock_shell)

    await git.push_to_branch("feature/test", "commit message")

    assert mock_shell.run_async.call_count == 3
    mock_shell.run_async.assert_any_call(["git", "add", "."], check=True)
    mock_shell.run_async.assert_any_call(["git", "commit", "-m", "commit message"], check=True)
    mock_shell.run_async.assert_any_call(["git", "push", "origin", "feature/test"], check=True)


@pytest.mark.asyncio
async def test_push_to_branch_failure() -> None:
    """Test push_to_branch failure."""
    mock_shell = MagicMock()
    result = CommandResult(1, "", "error")
    mock_shell.run_async = AsyncMock(side_effect=ShellError("Command failed", result))
    git = GitInterface(shell_executor=mock_shell)

    with pytest.raises(RuntimeError) as excinfo:
        await git.push_to_branch("feature/test", "msg")

    assert "Git push failed" in str(excinfo.value)
