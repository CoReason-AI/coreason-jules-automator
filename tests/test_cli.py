from unittest.mock import patch

from typer.testing import CliRunner

from coreason_jules_automator.cli import app, main

runner = CliRunner()


def test_run_help() -> None:
    """Test help command to verify app wiring."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_run_success() -> None:
    """Test successful run."""
    with patch("coreason_jules_automator.cli.Container"):
        # Mock asyncio.run to return success
        # Since we can't easily mock asyncio.run inside the function if we don't import it in test,
        # but cli.py imports asyncio. We can patch it in cli.py.
        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = (True, "Success")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            mock_asyncio_run.assert_called()
            # Verify orchestrator was called inside the coroutine passed to run
            # This is hard to verify exactly without running the coroutine,
            # but we can check that run was called with a coroutine object.

            # Alternatively, since we mock asyncio.run, the code inside orchestrator.run_cycle isn't executed
            # unless we execute the coroutine returned by the call.
            # But the test just checks the CLI exit code based on asyncio.run return value.


def test_run_failure() -> None:
    """Test failed run."""
    with patch("coreason_jules_automator.cli.Container"):
        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = (False, "Failure")

            result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])

            assert result.exit_code == 1


def test_run_exception() -> None:
    """Test run with unexpected exception."""
    # Use context managers for cleaner patching
    with (
        patch("coreason_jules_automator.cli.Container"),
        patch("coreason_jules_automator.cli.RichConsoleEmitter"),
        patch("coreason_jules_automator.cli.logger") as mock_logger,
        patch("coreason_jules_automator.cli.asyncio.run", side_effect=Exception("Crash inside try block")),
    ):
        result = runner.invoke(app, ["run", "Task", "--branch", "b"])

        assert result.exit_code == 1
        # Verify that our specific exception handler was triggered
        mock_logger.exception.assert_called()
        assert "Crash inside try block" in str(mock_logger.exception.call_args)


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
    with patch("coreason_jules_automator.cli.Container"):
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
    with patch("coreason_jules_automator.cli.Container"):
        with patch("coreason_jules_automator.cli.asyncio.run") as mock_asyncio_run:
            # asyncio.run returns None for campaign
            mock_asyncio_run.return_value = None

            result = runner.invoke(app, ["campaign", "Task1", "--base", "dev", "--count", "5"])

            if result.exit_code != 0:
                print(f"Output: {result.output}")

            assert result.exit_code == 0
            # Since we mocked asyncio.run, we can't check orchestrator calls directly unless we check args passed to run
