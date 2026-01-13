from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from typer.testing import CliRunner

from coreason_jules_automator.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()

def test_run_success(runner: CliRunner) -> None:
    """Test successful run."""
    with patch("coreason_jules_automator.cli.Orchestrator") as mock_orchestrator:
        instance = mock_orchestrator.return_value
        instance.run_cycle = AsyncMock(return_value=True)

        with patch("coreason_jules_automator.cli.ShellExecutor"), \
             patch("coreason_jules_automator.cli.GeminiInterface"), \
             patch("coreason_jules_automator.cli.GitInterface"), \
             patch("coreason_jules_automator.cli.GitHubInterface"), \
             patch("coreason_jules_automator.cli.LLMFactory"), \
             patch("coreason_jules_automator.cli.JanitorService"), \
             patch("coreason_jules_automator.cli.LocalDefenseStrategy"), \
             patch("coreason_jules_automator.cli.RemoteDefenseStrategy"), \
             patch("coreason_jules_automator.cli.JulesAgent"), \
             patch("coreason_jules_automator.cli.get_settings"):

             # Invoke without "run" subcommand as it seems to be the main command for this app object
             result = runner.invoke(app, ["Fix bug", "--branch", "feature/bugfix"])

             assert result.exit_code == 0
             instance.run_cycle.assert_called_once_with("Fix bug", "feature/bugfix")

def test_run_failure(runner: CliRunner) -> None:
    """Test run failure."""
    with patch("coreason_jules_automator.cli.Orchestrator") as mock_orchestrator:
        instance = mock_orchestrator.return_value
        instance.run_cycle = AsyncMock(return_value=False)

        with patch("coreason_jules_automator.cli.ShellExecutor"), \
             patch("coreason_jules_automator.cli.GeminiInterface"), \
             patch("coreason_jules_automator.cli.GitInterface"), \
             patch("coreason_jules_automator.cli.GitHubInterface"), \
             patch("coreason_jules_automator.cli.LLMFactory"), \
             patch("coreason_jules_automator.cli.JanitorService"), \
             patch("coreason_jules_automator.cli.LocalDefenseStrategy"), \
             patch("coreason_jules_automator.cli.RemoteDefenseStrategy"), \
             patch("coreason_jules_automator.cli.JulesAgent"), \
             patch("coreason_jules_automator.cli.get_settings"):

            result = runner.invoke(app, ["Fix bug", "--branch", "feature/bugfix"])

            assert result.exit_code == 1
