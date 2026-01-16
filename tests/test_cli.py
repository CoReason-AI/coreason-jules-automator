import sys
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

# Import the internal helper function for testing
from coreason_jules_automator.cli import app, main

runner = CliRunner()


def test_run_help() -> None:
    """Test help command to verify app wiring."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_run_success() -> None:
    """Test successful run."""
    with patch("coreason_jules_automator.cli.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value
        mock_orchestrator = mock_container.get_orchestrator.return_value

        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            # Mock asyncio.run to return success tuple
            mock_asyncio_run.return_value = (True, "Success")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_container.get_orchestrator.assert_called()
            mock_orchestrator.run_cycle.assert_called_with("Task1", "fix/bug")


def test_run_failure() -> None:
    """Test failed run."""
    with patch("coreason_jules_automator.cli.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value
        mock_orchestrator = mock_container.get_orchestrator.return_value

        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = (False, "Failure")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            assert result.exit_code == 1


def test_run_exception() -> None:
    """Test run with unexpected exception."""
    with patch("coreason_jules_automator.cli.OrchestratorContainer", side_effect=Exception("Crash")):
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
    with patch("coreason_jules_automator.cli.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value

        with (
            patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run,
            patch("coreason_jules_automator.cli.MarkdownReporter") as MockReporter,
            patch("coreason_jules_automator.cli.logger") as mock_logger,
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
    with patch("coreason_jules_automator.cli.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value
        mock_orchestrator = mock_container.get_orchestrator.return_value

        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            # asyncio.run returns None for campaign
            mock_asyncio_run.return_value = None

            result = runner.invoke(app, ["campaign", "Task1", "--base", "dev", "--count", "5"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_orchestrator.run_campaign.assert_called_with("Task1", "dev", 5)


def test_campaign_exception() -> None:
    """Test campaign with unexpected exception."""
    with patch("coreason_jules_automator.cli.OrchestratorContainer", side_effect=Exception("Campaign Crash")):
        result = runner.invoke(app, ["campaign", "Task1"])

        assert result.exit_code == 1


def test_campaign_default_count() -> None:
    """Test campaign command with default count (0/infinite)."""
    with patch("coreason_jules_automator.cli.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value
        mock_orchestrator = mock_container.get_orchestrator.return_value

        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = None

            result = runner.invoke(app, ["campaign", "Task1"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_orchestrator.run_campaign.assert_called_with("Task1", "develop", 0)
