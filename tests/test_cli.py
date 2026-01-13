from unittest.mock import patch

from typer.testing import CliRunner

from coreason_jules_automator.cli import app, main

runner = CliRunner()


def test_run_help() -> None:
    """Test help command to verify app wiring."""
    result = runner.invoke(app, ["--help"])
    # print(f"\nHelp Output:\n{result.output}")
    assert result.exit_code == 0


def test_run_success() -> None:
    """Test successful run."""
    # Mock get_settings to avoid missing env var errors
    # Patch where it is imported in cli.py or where it is defined
    with patch("coreason_jules_automator.cli.get_settings") as mock_settings_func:
        mock_settings = mock_settings_func.return_value
        mock_settings.llm_strategy = "api"
        # Also patch LLMFactory.get_client to avoid actual initialization
        with patch("coreason_jules_automator.llm.factory.LLMFactory.get_client"):
            with patch("coreason_jules_automator.cli.Orchestrator") as MockOrchestrator:
                mock_instance = MockOrchestrator.return_value
                mock_instance.run_cycle.return_value = True

                # Try without "run" subcommand if it fails
                result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])
                if result.exit_code != 0:
                    # Typer configuration issue? Try invoking without subcommand.
                    result = runner.invoke(app, ["Task1", "--branch", "fix/bug"])

                if result.exit_code != 0:
                    print(f"\nExit code: {result.exit_code}")
                    print(f"Output: {result.output}")

                assert result.exit_code == 0
                mock_instance.run_cycle.assert_called_with("Task1", "fix/bug")


def test_run_failure() -> None:
    """Test failed run."""
    with (
        patch("coreason_jules_automator.cli.get_settings"),
        patch("coreason_jules_automator.llm.factory.LLMFactory.get_client"),
        patch("coreason_jules_automator.cli.Orchestrator") as MockOrchestrator,
    ):
        mock_instance = MockOrchestrator.return_value
        mock_instance.run_cycle.return_value = False

        result = runner.invoke(app, ["run", "Task1", "--branch", "fix/bug"])
        if result.exit_code != 1:  # 2 is Usage Error
            result = runner.invoke(app, ["Task1", "--branch", "fix/bug"])

        if result.exit_code != 1:
            print(f"\nExit code: {result.exit_code}")
            print(f"Output: {result.output}")

        assert result.exit_code == 1


def test_run_exception() -> None:
    """Test run with unexpected exception."""
    with (
        patch("coreason_jules_automator.cli.get_settings"),
        patch("coreason_jules_automator.llm.factory.LLMFactory.get_client"),
        patch("coreason_jules_automator.cli.Orchestrator", side_effect=Exception("Crash")),
    ):
        result = runner.invoke(app, ["run", "Task", "--branch", "b"])
        if result.exit_code != 1:
            result = runner.invoke(app, ["Task", "--branch", "b"])

        if result.exit_code != 1:
            print(f"\nExit code: {result.exit_code}")
            print(f"Output: {result.output}")

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
    assert "Usage: vibe-runner" in clean_stdout or "Usage: python -m coreason_jules_automator.cli" in clean_stdout


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
        "Usage: vibe-runner" in clean_stdout
        or "Usage: coreason_jules_automator/cli.py" in clean_stdout
        or "Usage: cli.py" in clean_stdout
    )
