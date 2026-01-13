import subprocess
from unittest.mock import MagicMock, patch

import pytest
from coreason_jules_automator.utils.shell import ShellExecutor, ShellError, CommandResult


@pytest.fixture
def executor() -> ShellExecutor:
    return ShellExecutor()


def test_run_success(executor: ShellExecutor) -> None:
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "output"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        result = executor.run(["echo", "hello"])

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        mock_run.assert_called_with(
            ["echo", "hello"],
            capture_output=True,
            text=True,
            check=False,
            timeout=300
        )


def test_run_failure_no_check(executor: ShellExecutor) -> None:
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "error"
        mock_run.return_value = mock_process

        result = executor.run(["ls", "nonexistent"])

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == "error"


def test_run_failure_check(executor: ShellExecutor) -> None:
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = ""
        mock_process.stderr = "error"
        mock_run.return_value = mock_process

        with pytest.raises(ShellError) as excinfo:
            executor.run(["ls", "nonexistent"], check=True)

        assert "Command failed with exit code 1" in str(excinfo.value)
        assert excinfo.value.result.stderr == "error"


def test_run_timeout(executor: ShellExecutor) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["sleep"], 1)):
        result = executor.run(["sleep", "1"])
        assert result.exit_code == -1
        assert "Command timed out" in result.stderr


def test_run_timeout_check(executor: ShellExecutor) -> None:
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["sleep"], 1)):
        with pytest.raises(ShellError) as excinfo:
            executor.run(["sleep", "1"], check=True)
        assert "Command timed out" in str(excinfo.value)


def test_run_exception(executor: ShellExecutor) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError("No file")):
        result = executor.run(["badcmd"])
        assert result.exit_code == -1
        assert "No file" in result.stderr


def test_run_exception_check(executor: ShellExecutor) -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError("No file")):
        with pytest.raises(ShellError) as excinfo:
            executor.run(["badcmd"], check=True)
        assert "Failed to execute command" in str(excinfo.value)
