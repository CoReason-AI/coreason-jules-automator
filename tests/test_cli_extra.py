import sys
from unittest.mock import AsyncMock, patch
import pytest
from typer.testing import CliRunner
from coreason_jules_automator.cli import app

@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()

def test_run_success_exit_code(runner: CliRunner) -> None:
    """Test successful run triggers sys.exit(0)."""
    with patch("coreason_jules_automator.cli.Orchestrator") as mock_orchestrator:
        instance = mock_orchestrator.return_value
        instance.run_cycle = AsyncMock(return_value=True)

        with (
            patch("coreason_jules_automator.cli.ShellExecutor"),
            patch("coreason_jules_automator.cli.GeminiInterface"),
            patch("coreason_jules_automator.cli.GitInterface"),
            patch("coreason_jules_automator.cli.GitHubInterface"),
            patch("coreason_jules_automator.cli.LLMFactory"),
            patch("coreason_jules_automator.cli.JanitorService"),
            patch("coreason_jules_automator.cli.LocalDefenseStrategy"),
            patch("coreason_jules_automator.cli.RemoteDefenseStrategy"),
            patch("coreason_jules_automator.cli.JulesAgent"),
            patch("coreason_jules_automator.cli.get_settings"),
            # Do NOT patch sys.exit. Let CliRunner handle it.
        ):
            result = runner.invoke(app, ["Task", "--branch", "branch"])
            assert result.exit_code == 0


def test_run_failure_exit_code(runner: CliRunner) -> None:
    """Test failed run triggers sys.exit(1)."""
    with patch("coreason_jules_automator.cli.Orchestrator") as mock_orchestrator:
        instance = mock_orchestrator.return_value
        instance.run_cycle = AsyncMock(return_value=False)

        with (
            patch("coreason_jules_automator.cli.ShellExecutor"),
            patch("coreason_jules_automator.cli.GeminiInterface"),
            patch("coreason_jules_automator.cli.GitInterface"),
            patch("coreason_jules_automator.cli.GitHubInterface"),
            patch("coreason_jules_automator.cli.LLMFactory"),
            patch("coreason_jules_automator.cli.JanitorService"),
            patch("coreason_jules_automator.cli.LocalDefenseStrategy"),
            patch("coreason_jules_automator.cli.RemoteDefenseStrategy"),
            patch("coreason_jules_automator.cli.JulesAgent"),
            patch("coreason_jules_automator.cli.get_settings"),
            # Do NOT patch sys.exit. Let CliRunner handle it.
        ):
            result = runner.invoke(app, ["Task", "--branch", "branch"])
            assert result.exit_code == 1
