from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.utils.shell import CommandResult, ShellError


@pytest.fixture
def gemini() -> GeminiInterface:
    return GeminiInterface()


def test_init_checks_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that init checks for executable."""
    with patch("shutil.which", return_value=None):
        with patch("coreason_jules_automator.interfaces.gemini.logger") as mock_logger:
            GeminiInterface()
            mock_logger.warning.assert_called_with("Gemini executable 'gemini' not found in PATH.")

    with patch("shutil.which", return_value="/usr/bin/gemini"):
        with patch("coreason_jules_automator.interfaces.gemini.logger") as mock_logger:
            GeminiInterface()
            mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_run_command_success(gemini: GeminiInterface) -> None:
    """Test successful command execution."""
    mock_shell = MagicMock()
    mock_shell.run_async = AsyncMock(return_value=CommandResult(0, "Scan complete. No issues found.", ""))
    gemini.shell = mock_shell

    output = await gemini._run_command(["test", "arg"])

    assert output == "Scan complete. No issues found."
    mock_shell.run_async.assert_called_once_with(["gemini", "test", "arg"], check=True)


@pytest.mark.asyncio
async def test_run_command_failure_exit_code(gemini: GeminiInterface) -> None:
    """Test command failure with non-zero exit code."""
    mock_shell = MagicMock()
    result = CommandResult(1, "", "Critical vulnerability found.")
    mock_shell.run_async = AsyncMock(side_effect=ShellError("Command failed", result))
    gemini.shell = mock_shell

    with pytest.raises(RuntimeError) as excinfo:
        await gemini._run_command(["test", "fail"])

    assert "Gemini command failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_run_command_failure_exception(gemini: GeminiInterface) -> None:
    """Test command failure when subprocess raises exception."""
    mock_shell = MagicMock()
    # ShellError is what ShellExecutor raises.
    mock_shell.run_async = AsyncMock(side_effect=ShellError("Exec format error", CommandResult(-1, "", "")))
    gemini.shell = mock_shell

    with pytest.raises(RuntimeError) as excinfo:
        await gemini._run_command(["test", "crash"])

    assert "Gemini command failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_security_scan(gemini: GeminiInterface) -> None:
    """Test security_scan calls _run_command correctly."""
    with patch.object(gemini, "_run_command", return_value="Scan passed") as mock_run:
        result = await gemini.security_scan("src/")

        assert result == "Scan passed"
        mock_run.assert_called_once_with(["security", "scan", "src/"])


@pytest.mark.asyncio
async def test_code_review(gemini: GeminiInterface) -> None:
    """Test code_review calls _run_command correctly."""
    with patch.object(gemini, "_run_command", return_value="Review passed") as mock_run:
        result = await gemini.code_review("src/")

        assert result == "Review passed"
        mock_run.assert_called_once_with(["code-review", "src/"])
