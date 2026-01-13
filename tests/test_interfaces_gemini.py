from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.interfaces.gemini import GeminiInterface


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


def test_run_command_success(gemini: GeminiInterface) -> None:
    """Test successful command execution."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Scan complete. No issues found."
        mock_run.return_value = mock_result

        output = gemini._run_command(["test", "arg"])

        assert output == "Scan complete. No issues found."
        mock_run.assert_called_once_with(["gemini", "test", "arg"], capture_output=True, text=True, check=False, timeout=300)


def test_run_command_failure_exit_code(gemini: GeminiInterface) -> None:
    """Test command failure with non-zero exit code."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Critical vulnerability found."
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError) as excinfo:
            gemini._run_command(["test", "fail"])

        assert "Gemini command failed" in str(excinfo.value)
        assert "Critical vulnerability found" in str(excinfo.value)


def test_run_command_failure_exception(gemini: GeminiInterface) -> None:
    """Test command failure when subprocess raises exception."""
    with patch("subprocess.run", side_effect=OSError("Exec format error")):
        with pytest.raises(RuntimeError) as excinfo:
            gemini._run_command(["test", "crash"])

        assert "Gemini command failed" in str(excinfo.value)


def test_security_scan(gemini: GeminiInterface) -> None:
    """Test security_scan calls _run_command correctly."""
    with patch.object(gemini, "_run_command", return_value="Scan passed") as mock_run:
        result = gemini.security_scan("src/")

        assert result == "Scan passed"
        mock_run.assert_called_once_with(["security", "scan", "src/"])


def test_code_review(gemini: GeminiInterface) -> None:
    """Test code_review calls _run_command correctly."""
    with patch.object(gemini, "_run_command", return_value="Review passed") as mock_run:
        result = gemini.code_review("src/")

        assert result == "Review passed"
        mock_run.assert_called_once_with(["code-review", "src/"])
