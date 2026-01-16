import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

# Import the internal helper function for testing
from coreason_jules_automator.cli import _get_async_llm_client, app, main

runner = CliRunner()


def test_run_help() -> None:
    """Test help command to verify app wiring."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_run_success() -> None:
    """Test successful run."""
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"

        with (
            patch("coreason_jules_automator.cli.AsyncOrchestrator") as MockOrchestrator,
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.AsyncGitInterface"),
            patch("coreason_jules_automator.cli.AsyncGitHubInterface"),
            patch("coreason_jules_automator.cli.AsyncGeminiInterface"),
            patch("coreason_jules_automator.cli.AsyncJulesAgent"),
            patch("coreason_jules_automator.cli.AsyncShellExecutor"),
            patch("coreason_jules_automator.cli._get_async_llm_client"),
        ):
            mock_instance = MockOrchestrator.return_value
            # Mock asyncio.run to return success tuple
            mock_asyncio_run.return_value = (True, "Success")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_instance.run_cycle.assert_called_with("Task1", "fix/bug")
            mock_asyncio_run.assert_called()


def test_run_failure() -> None:
    """Test failed run."""
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"

        with (
            patch("coreason_jules_automator.cli.AsyncOrchestrator"),
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.AsyncGitInterface"),
            patch("coreason_jules_automator.cli.AsyncGitHubInterface"),
            patch("coreason_jules_automator.cli.AsyncGeminiInterface"),
            patch("coreason_jules_automator.cli.AsyncJulesAgent"),
            patch("coreason_jules_automator.cli.AsyncShellExecutor"),
            patch("coreason_jules_automator.cli._get_async_llm_client"),
        ):
            mock_asyncio_run.return_value = (False, "Failure")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            assert result.exit_code == 1


def test_run_exception() -> None:
    """Test run with unexpected exception."""
    with (
        patch("coreason_jules_automator.cli.get_settings"),
        patch("coreason_jules_automator.cli.AsyncShellExecutor", side_effect=Exception("Crash")),
    ):
        result = runner.invoke(app, ["run", "Task", "--branch", "b"])

        assert result.exit_code == 1


def test_main() -> None:
    """Test main function."""
    with patch("coreason_jules_automator.cli.app") as mock_app:
        main()
        mock_app.assert_called_once()


def test_main_execution() -> None:
    """Test executing the module as a script."""
    import re
    import subprocess
    import sys

    # Use coverage run to ensure we capture the coverage
    cmd = [sys.executable, "-m", "coverage", "run", "--append", "-m", "coreason_jules_automator.cli", "--help"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    # Strip ANSI codes
    clean_stdout = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", result.stdout)
    assert (
        "Usage: coreason-jules-automator" in clean_stdout
        or "Usage: python -m coreason_jules_automator.cli" in clean_stdout
    )


def test_cli_file_execution() -> None:
    """Test executing the cli.py file directly."""
    import re
    import subprocess
    import sys
    from pathlib import Path

    # Locate the cli.py file
    cli_file = Path("src/coreason_jules_automator/cli.py").resolve()

    # Use coverage run here too
    cmd = [sys.executable, "-m", "coverage", "run", "--append", str(cli_file), "--help"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0
    # Strip ANSI codes
    clean_stdout = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", result.stdout)
    assert (
        "Usage: coreason-jules-automator" in clean_stdout
        or "Usage: coreason_jules_automator/cli.py" in clean_stdout
        or "Usage: cli.py" in clean_stdout
    )


def test_run_report_exception() -> None:
    """Test run with exception during report generation."""
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"

        with (
            patch("coreason_jules_automator.cli.AsyncOrchestrator"),
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.MarkdownReporter") as MockReporter,
            patch("coreason_jules_automator.cli.logger") as mock_logger,
            patch("coreason_jules_automator.cli.AsyncGitInterface"),
            patch("coreason_jules_automator.cli.AsyncGitHubInterface"),
            patch("coreason_jules_automator.cli.AsyncGeminiInterface"),
            patch("coreason_jules_automator.cli.AsyncJulesAgent"),
            patch("coreason_jules_automator.cli.AsyncShellExecutor"),
            patch("coreason_jules_automator.cli._get_async_llm_client"),
        ):
            mock_asyncio_run.return_value = (True, "Success")

            mock_reporter = MockReporter.return_value
            mock_reporter.generate_report.side_effect = Exception("Report Error")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_logger.error.assert_called_with("Failed to generate report: Report Error")


def test_campaign_command() -> None:
    """Test campaign command."""
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"

        with (
            patch("coreason_jules_automator.cli.AsyncOrchestrator") as MockOrchestrator,
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.AsyncGitInterface"),
            patch("coreason_jules_automator.cli.AsyncGitHubInterface"),
            patch("coreason_jules_automator.cli.AsyncGeminiInterface"),
            patch("coreason_jules_automator.cli.JanitorService"),
            patch("coreason_jules_automator.cli.AsyncJulesAgent"),
            patch("coreason_jules_automator.cli.AsyncShellExecutor"),
            patch("coreason_jules_automator.cli._get_async_llm_client"),
        ):
            mock_instance = MockOrchestrator.return_value
            # asyncio.run returns None for campaign
            mock_asyncio_run.return_value = None

            result = runner.invoke(app, ["campaign", "Task1", "--base", "dev", "--count", "5"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_instance.run_campaign.assert_called_with("Task1", "dev", 5)


def test_campaign_exception() -> None:
    """Test campaign with unexpected exception."""
    with (
        patch("coreason_jules_automator.cli.get_settings"),
        patch("coreason_jules_automator.cli.AsyncShellExecutor", side_effect=Exception("Campaign Crash")),
    ):
        result = runner.invoke(app, ["campaign", "Task1"])

        assert result.exit_code == 1


def test_campaign_default_count() -> None:
    """Test campaign command with default count (0/infinite)."""
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"

        with (
            patch("coreason_jules_automator.cli.AsyncOrchestrator") as MockOrchestrator,
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.AsyncGitInterface"),
            patch("coreason_jules_automator.cli.AsyncGitHubInterface"),
            patch("coreason_jules_automator.cli.AsyncGeminiInterface"),
            patch("coreason_jules_automator.cli.JanitorService"),
            patch("coreason_jules_automator.cli.AsyncJulesAgent"),
            patch("coreason_jules_automator.cli.AsyncShellExecutor"),
            patch("coreason_jules_automator.cli._get_async_llm_client"),
        ):
            mock_instance = MockOrchestrator.return_value
            mock_asyncio_run.return_value = None

            result = runner.invoke(app, ["campaign", "Task1"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_instance.run_campaign.assert_called_with("Task1", "develop", 0)


# --- Coverage Tests for _get_async_llm_client ---


def test_get_async_llm_client_openai_import_error() -> None:
    """Test helper when openai is not installed."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"

    with patch.dict(sys.modules, {"openai": None}):
        result = _get_async_llm_client(mock_settings)
        assert result is None


def test_get_async_llm_client_deepseek() -> None:
    """Test helper with DeepSeek key."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY.get_secret_value.return_value = "ds-key"
    mock_settings.OPENAI_API_KEY = None

    with patch("openai.AsyncOpenAI") as MockOpenAI:
        result = _get_async_llm_client(mock_settings)
        assert result is not None
        MockOpenAI.assert_called_with(api_key="ds-key", base_url="https://api.deepseek.com")


def test_get_async_llm_client_openai() -> None:
    """Test helper with OpenAI key."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY = None
    mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "oa-key"

    with patch("openai.AsyncOpenAI") as MockOpenAI:
        result = _get_async_llm_client(mock_settings)
        assert result is not None
        MockOpenAI.assert_called_with(api_key="oa-key")


def test_get_async_llm_client_no_keys() -> None:
    """Test helper with API strategy but no keys."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY = None
    mock_settings.OPENAI_API_KEY = None

    # Ensure openai module exists
    with patch("openai.AsyncOpenAI"):
        result = _get_async_llm_client(mock_settings)
        assert result is None


def test_get_async_llm_client_local() -> None:
    """Test helper with local strategy."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "local"

    result = _get_async_llm_client(mock_settings)
    assert result is None
