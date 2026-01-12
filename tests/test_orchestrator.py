from typing import Any
from unittest.mock import patch

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


def test_line_1_defense_success(orchestrator: Any) -> None:
    """Test Line 1 passes when checks succeed."""
    # Mocks are already set up by fixture init
    # Configure them to not raise exceptions
    assert orchestrator._line_1_defense() is True
    orchestrator.gemini.security_scan.assert_called_once()
    orchestrator.gemini.code_review.assert_called_once()


def test_line_1_defense_security_fail(orchestrator: Any) -> None:
    """Test Line 1 fails when security scan fails."""
    orchestrator.gemini.security_scan.side_effect = RuntimeError("Security Fail")
    assert orchestrator._line_1_defense() is False
    orchestrator.gemini.code_review.assert_not_called()  # Short circuits? No, separate checks in implementation logic.
    # Actually logic is: if security fails, return False immediately?
    # Let's check implementation:
    # if security: try... except return False.
    # So yes, it returns False immediately.


def test_line_1_defense_review_fail(orchestrator: Any) -> None:
    """Test Line 1 fails when code review fails."""
    orchestrator.gemini.code_review.side_effect = RuntimeError("Review Fail")
    assert orchestrator._line_1_defense() is False


def test_line_2_defense_success(orchestrator: Any) -> None:
    """Test Line 2 passes when CI succeeds."""
    orchestrator.janitor.sanitize_commit.return_value = "clean commit"
    # Mock checks: first queued, then success
    orchestrator.github.get_pr_checks.side_effect = [
        [],  # Not started
        [{"status": "queued", "conclusion": None}],
        [{"status": "completed", "conclusion": "success"}],
    ]

    with patch("time.sleep"):  # Don't sleep
        assert orchestrator._line_2_defense("feature/1") is True

    orchestrator.github.push_to_branch.assert_called_with("feature/1", "clean commit")


def test_line_2_defense_push_fail(orchestrator: Any) -> None:
    """Test Line 2 fails if push fails."""
    orchestrator.github.push_to_branch.side_effect = RuntimeError("Push Fail")
    assert orchestrator._line_2_defense("feature/1") is False


def test_line_2_defense_ci_fail(orchestrator: Any) -> None:
    """Test Line 2 fails if CI fails."""
    orchestrator.github.get_pr_checks.return_value = [
        {"name": "test", "status": "completed", "conclusion": "failure", "url": "http://fail"}
    ]
    orchestrator.janitor.summarize_logs.return_value = "Fix it."

    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is False

    orchestrator.janitor.summarize_logs.assert_called()


def test_line_2_defense_timeout(orchestrator: Any) -> None:
    """Test Line 2 fails if checks never complete."""
    orchestrator.github.get_pr_checks.return_value = [{"status": "queued", "conclusion": None}]

    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is False


def test_run_cycle_success(orchestrator: Any) -> None:
    """Test full cycle success."""
    with (
        patch.object(orchestrator, "_line_1_defense", return_value=True),
        patch.object(orchestrator, "_line_2_defense", return_value=True),
    ):
        assert orchestrator.run_cycle("task", "branch") is True
        orchestrator.agent.start.assert_called_with("task")


def test_run_cycle_agent_fail(orchestrator: Any) -> None:
    """Test cycle aborts if agent fails."""
    orchestrator.agent.start.side_effect = Exception("Agent died")
    assert orchestrator.run_cycle("task", "branch") is False


def test_run_cycle_line_1_retry(orchestrator: Any) -> None:
    """Test retry loop on Line 1 failure."""
    # Fail once, then pass
    with (
        patch.object(orchestrator, "_line_1_defense", side_effect=[False, True]),
        patch.object(orchestrator, "_line_2_defense", return_value=True),
    ):
        assert orchestrator.run_cycle("task", "branch") is True
        assert orchestrator.agent.start.call_count == 2


def test_run_cycle_max_retries(orchestrator: Any) -> None:
    """Test max retries reached."""
    # Always fail Line 1
    with patch.object(orchestrator, "_line_1_defense", return_value=False):
        # Mock settings max_retries to 2 for speed
        with patch("coreason_jules_automator.orchestrator.settings") as mock_settings:
            mock_settings.max_retries = 2
            assert orchestrator.run_cycle("task", "branch") is False
            assert orchestrator.agent.start.call_count == 2


def test_line_2_poll_exception(orchestrator: Any) -> None:
    """Test polling exceptions (line 152 coverage)."""
    # Throw error then succeed
    orchestrator.github.get_pr_checks.side_effect = [
        RuntimeError("Poll error"),
        [{"status": "completed", "conclusion": "success"}],
    ]
    with patch("time.sleep"):
        assert orchestrator._line_2_defense("feature/1") is True


def test_handle_ci_failure_no_check_found(orchestrator: Any) -> None:
    """Test failure handler when no specific check failure is identified (unlikely but logic path coverage)."""
    orchestrator._handle_ci_failure([])
    orchestrator.janitor.summarize_logs.assert_not_called()

    orchestrator._handle_ci_failure([{"conclusion": "success"}])
    orchestrator.janitor.summarize_logs.assert_not_called()


def test_orchestrator_line_1_defense_review_fail_coverage() -> None:
    """Explicit test to hit orchestrator.py line 70."""
    from coreason_jules_automator.orchestrator import Orchestrator

    with patch("coreason_jules_automator.orchestrator.settings") as mock_settings:
        mock_settings.extensions_enabled = ["code-review"]
        mock_settings.max_retries = 1

        with patch("coreason_jules_automator.orchestrator.GeminiInterface") as MockGemini:
            mock_gemini = MockGemini.return_value
            mock_gemini.code_review.side_effect = RuntimeError("Fail")

            with (
                patch("coreason_jules_automator.orchestrator.GitHubInterface"),
                patch("coreason_jules_automator.orchestrator.LLMProvider"),
                patch("coreason_jules_automator.orchestrator.JulesAgent"),
            ):
                orch = Orchestrator()
                assert orch._line_1_defense() is False
