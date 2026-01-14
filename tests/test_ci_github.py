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


def test_get_latest_run_log_success(gh: GitHubInterface) -> None:
    """Test get_latest_run_log success."""
    with patch.object(gh, "_run_command") as mock_run:
        mock_run.side_effect = [
            '[{"databaseId": 12345}]',  # run list output
            "Log content...",  # run view output
        ]

        log = gh.get_latest_run_log("feature/test")

        assert log == "Log content..."
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["run", "list", "--branch", "feature/test", "--limit", "1", "--json", "databaseId"])
        mock_run.assert_any_call(["run", "view", "12345", "--log"])


def test_get_latest_run_log_no_runs(gh: GitHubInterface) -> None:
    """Test get_latest_run_log when no runs found."""
    with patch.object(gh, "_run_command", return_value="[]"):
        log = gh.get_latest_run_log("feature/test")
        assert log == "No workflow runs found."


def test_get_latest_run_log_json_error(gh: GitHubInterface) -> None:
    """Test get_latest_run_log handles json error."""
    with patch.object(gh, "_run_command", return_value="invalid json"):
        log = gh.get_latest_run_log("feature/test")
        assert "Failed to parse run list" in log
