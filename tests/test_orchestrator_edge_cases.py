from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from coreason_jules_automator.orchestrator import Orchestrator


@pytest.fixture
def orchestrator() -> Any:
    # Patch all dependencies to avoid real interactions
    with (
        patch("coreason_jules_automator.orchestrator.GeminiInterface"),
        patch("coreason_jules_automator.orchestrator.GitHubInterface"),
        patch("coreason_jules_automator.orchestrator.LLMProvider"),
        patch("coreason_jules_automator.orchestrator.JulesAgent"),
    ):
        return Orchestrator()


def test_run_cycle_zero_retries(orchestrator: Any) -> None:
    """Test run_cycle when max_retries is set to 0."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 0
        mock_get_settings.return_value = mock_settings

        result = orchestrator.run_cycle("task", "branch")
        assert result is False
        orchestrator.agent.start.assert_not_called()


def test_line_1_defense_no_extensions(orchestrator: Any) -> None:
    """Test Line 1 defense when no extensions are enabled."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.extensions_enabled = []
        mock_get_settings.return_value = mock_settings

        assert orchestrator._line_1_defense() is True
        orchestrator.gemini.security_scan.assert_not_called()
        orchestrator.gemini.code_review.assert_not_called()


def test_line_2_defense_complex_polling(orchestrator: Any) -> None:
    """Test Line 2 defense with a sequence of check statuses."""
    orchestrator.janitor.sanitize_commit.return_value = "clean commit"
    # Sequence: Queued -> In Progress -> Success
    orchestrator.github.get_pr_checks.side_effect = [
        [{"status": "queued", "conclusion": None}],
        [{"status": "in_progress", "conclusion": None}],
        [{"status": "completed", "conclusion": "success"}],
    ]

    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is True


def test_line_2_defense_malformed_data(orchestrator: Any) -> None:
    """Test Line 2 defense crashes with malformed check data (missing 'status')."""
    orchestrator.janitor.sanitize_commit.return_value = "clean commit"
    # Check missing 'status' key
    orchestrator.github.get_pr_checks.return_value = [{"conclusion": "success"}]

    with patch("time.sleep"):
        with pytest.raises(KeyError):
            orchestrator._line_2_defense("feature/1")


def test_line_2_defense_multiple_failures(orchestrator: Any) -> None:
    """Test Line 2 defense with multiple failed checks."""
    orchestrator.janitor.sanitize_commit.return_value = "clean commit"
    orchestrator.github.get_pr_checks.return_value = [
        {"name": "check1", "status": "completed", "conclusion": "failure", "url": "url1"},
        {"name": "check2", "status": "completed", "conclusion": "failure", "url": "url2"},
    ]
    orchestrator.janitor.summarize_logs.return_value = "Fix both."

    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is False

    # Verify summary called (checking for interaction, not specific check picked as it picks the first failure found)
    orchestrator.janitor.summarize_logs.assert_called()


def test_line_2_defense_mixed_statuses_and_failures(orchestrator: Any) -> None:
    """Test Line 2 defense with mixed statuses and eventual failure."""
    orchestrator.janitor.sanitize_commit.return_value = "clean commit"

    # 1. One completed success, one in progress
    # 2. One completed success, one completed failure
    orchestrator.github.get_pr_checks.side_effect = [
        [
            {"name": "check1", "status": "completed", "conclusion": "success"},
            {"name": "check2", "status": "in_progress", "conclusion": None}
        ],
        [
            {"name": "check1", "status": "completed", "conclusion": "success"},
            {"name": "check2", "status": "completed", "conclusion": "failure", "url": "url2"},
        ],
    ]

    orchestrator.janitor.summarize_logs.return_value = "Fix check2."

    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is False

    orchestrator.janitor.summarize_logs.assert_called()
