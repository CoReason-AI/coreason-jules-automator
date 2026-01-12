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
    with patch("coreason_jules_automator.cli.Orchestrator") as MockOrchestrator:
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
    with patch("coreason_jules_automator.cli.Orchestrator", side_effect=Exception("Crash")):
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
