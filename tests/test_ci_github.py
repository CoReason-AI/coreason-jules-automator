import subprocess
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.ci.github import GitHubInterface


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


def test_run_command_success(gh: GitHubInterface) -> None:
    """Test successful command execution."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_run.return_value = mock_result

        output = gh._run_command(["test"])

        assert output == "output"
        mock_run.assert_called_once()


def test_run_command_failure_exit_code(gh: GitHubInterface) -> None:
    """Test command failure with exit code."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError) as excinfo:
            gh._run_command(["test"])

        assert "gh command failed" in str(excinfo.value)


def test_run_command_exception(gh: GitHubInterface) -> None:
    """Test command failure with exception (e.g. not found)."""
    with patch("subprocess.run", side_effect=OSError("Not found")):
        with pytest.raises(RuntimeError) as excinfo:
            gh._run_command(["test"])

        assert "gh command failed" in str(excinfo.value)


def test_get_pr_checks_success(gh: GitHubInterface) -> None:
    """Test get_pr_checks parsing."""
    json_output = '[{"name": "test", "status": "completed", "conclusion": "success"}]'
    with patch.object(gh, "_run_command", return_value=json_output) as mock_run:
        checks = gh.get_pr_checks()
        assert checks == [{"name": "test", "status": "completed", "conclusion": "success"}]
        mock_run.assert_called_with(["pr", "checks", "--json", "bucket,name,status,conclusion,url"])


def test_get_pr_checks_invalid_json(gh: GitHubInterface) -> None:
    """Test get_pr_checks with invalid json."""
    with patch.object(gh, "_run_command", return_value="invalid json"):
        with pytest.raises(RuntimeError) as excinfo:
            gh.get_pr_checks()
        assert "Failed to parse gh output" in str(excinfo.value)


def test_get_pr_checks_unexpected_format(gh: GitHubInterface) -> None:
    """Test get_pr_checks when output is valid JSON but not a list."""
    with patch.object(gh, "_run_command", return_value="{}"):
        with pytest.raises(RuntimeError) as excinfo:
            gh.get_pr_checks()
        assert "Unexpected format from gh: expected list" in str(excinfo.value)


def test_push_to_branch_success(gh: GitHubInterface) -> None:
    """Test push_to_branch success."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        gh.push_to_branch("feature/test", "commit message")
        assert mock_run.call_count == 3  # add, commit, push
        # Verify calls
        mock_run.assert_any_call(["git", "add", "."], capture_output=True, text=True, check=False, timeout=300)
        mock_run.assert_any_call(["git", "commit", "-m", "commit message"], capture_output=True, text=True, check=False, timeout=300)
        mock_run.assert_any_call(["git", "push", "origin", "feature/test"], capture_output=True, text=True, check=False, timeout=300)


def test_push_to_branch_failure(gh: GitHubInterface) -> None:
    """Test push_to_branch failure."""
    # Create a CalledProcessError with stderr
    err = subprocess.CalledProcessError(1, ["git", "push"])
    err.stderr = b"remote rejected"

    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError) as excinfo:
            gh.push_to_branch("feature/test", "msg")
        assert "Git push failed" in str(excinfo.value)


def test_push_to_branch_failure_with_stderr(gh: GitHubInterface) -> None:
    """Test push_to_branch failure with stderr to cover error decoding."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Permission denied"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError) as excinfo:
            gh.push_to_branch("feature/test", "msg")
        assert "Git push failed: Command failed with exit code 1: Permission denied" in str(excinfo.value)


def test_push_to_branch_failure_no_stderr(gh: GitHubInterface) -> None:
    """Test push_to_branch failure with no stderr."""
    # Create a CalledProcessError without stderr
    err = subprocess.CalledProcessError(1, ["git", "push"])
    err.stderr = None

    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError) as excinfo:
            gh.push_to_branch("feature/test", "msg")
        assert "Git push failed" in str(excinfo.value)
