from unittest.mock import MagicMock, patch, AsyncMock
import json
import pytest

from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.utils.shell import CommandResult, ShellError


@pytest.fixture
def gh() -> GitHubInterface:
    return GitHubInterface()


def test_init_checks_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that init checks for executable."""
    with patch("shutil.which", return_value=None):
        with patch("coreason_jules_automator.ci.github.logger") as mock_logger:
            GitHubInterface()
            mock_logger.warning.assert_called_with("GitHub CLI executable 'gh' not found in PATH.")

    with patch("shutil.which", return_value="/usr/bin/gh"):
        with patch("coreason_jules_automator.ci.github.logger") as mock_logger:
            GitHubInterface()
            mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_run_command_success(gh: GitHubInterface) -> None:
    """Test successful command execution."""
    mock_shell = MagicMock()
    mock_shell.run_async = AsyncMock(return_value=CommandResult(0, "output", ""))
    gh.shell = mock_shell

    output = await gh._run_command(["test"])

    assert output == "output"
    mock_shell.run_async.assert_called_once()


@pytest.mark.asyncio
async def test_run_command_failure_exit_code(gh: GitHubInterface) -> None:
    """Test command failure with exit code."""
    mock_shell = MagicMock()
    result = CommandResult(1, "", "error")
    mock_shell.run_async = AsyncMock(side_effect=ShellError("Command failed", result))
    gh.shell = mock_shell

    with pytest.raises(RuntimeError) as excinfo:
        await gh._run_command(["test"])

    assert "gh command failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_command_exception(gh: GitHubInterface) -> None:
    """Test command failure with exception (e.g. not found)."""
    # Assuming the shell executor raises an exception (other than ShellError, which is caught)
    # But shell executor run_async catches everything and returns result, so typically check=True raises ShellError.
    # The current implementation of _run_command calls run_async(check=True), which raises ShellError.
    # If run_async itself raises something else, it bubble up as runtime error in _run_command wrapper? No.
    # The implementation:
    # try:
    #     result = await self.shell.run_async(command, check=True)
    # except ShellError as e:

    mock_shell = MagicMock()
    mock_shell.run_async = AsyncMock(side_effect=ShellError("Not found", CommandResult(-1, "", "")))
    gh.shell = mock_shell

    with pytest.raises(RuntimeError) as excinfo:
        await gh._run_command(["test"])

    assert "gh command failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_pr_checks_success(gh: GitHubInterface) -> None:
    """Test get_pr_checks parsing."""
    json_output = '[{"name": "test", "status": "completed", "conclusion": "success"}]'
    with patch.object(gh, "_run_command", return_value=json_output) as mock_run:
        checks = await gh.get_pr_checks()
        assert checks == [{"name": "test", "status": "completed", "conclusion": "success"}]
        mock_run.assert_called_with(["pr", "checks", "--json", "bucket,name,status,conclusion,url"])


@pytest.mark.asyncio
async def test_get_pr_checks_invalid_json(gh: GitHubInterface) -> None:
    """Test get_pr_checks with invalid json."""
    with patch.object(gh, "_run_command", return_value="invalid json") as mock_run:
        with pytest.raises(RuntimeError) as excinfo:
            await gh.get_pr_checks()
        assert "Failed to parse gh output" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_pr_checks_unexpected_format(gh: GitHubInterface) -> None:
    """Test get_pr_checks when output is valid JSON but not a list."""
    with patch.object(gh, "_run_command", return_value="{}") as mock_run:
        with pytest.raises(RuntimeError) as excinfo:
            await gh.get_pr_checks()
        assert "Unexpected format from gh: expected list" in str(excinfo.value)
