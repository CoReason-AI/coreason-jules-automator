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
        # We need to ensure settings is also mocked or valid during init if it calls get_settings
        # Orchestrator doesn't call get_settings in init, but methods do.
        return Orchestrator()


def test_line_1_defense_success(orchestrator: Any) -> None:
    """Test Line 1 passes when checks succeed."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.extensions_enabled = ["security", "code-review"]
        mock_get_settings.return_value = mock_settings

        assert orchestrator._line_1_defense() is True
        orchestrator.gemini.security_scan.assert_called_once()
        orchestrator.gemini.code_review.assert_called_once()


def test_line_1_defense_security_fail(orchestrator: Any) -> None:
    """Test Line 1 fails when security scan fails."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.extensions_enabled = ["security", "code-review"]
        mock_get_settings.return_value = mock_settings

        orchestrator.gemini.security_scan.side_effect = RuntimeError("Security Fail")
        assert orchestrator._line_1_defense() is False
        orchestrator.gemini.code_review.assert_not_called()


def test_line_1_defense_review_fail(orchestrator: Any) -> None:
    """Test Line 1 fails when code review fails."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.extensions_enabled = ["security", "code-review"]
        mock_get_settings.return_value = mock_settings

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
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        with (
            patch.object(orchestrator, "_line_1_defense", return_value=True),
            patch.object(orchestrator, "_line_2_defense", return_value=True),
        ):
            assert orchestrator.run_cycle("task", "branch") is True
            orchestrator.agent.start.assert_called_with("task")


def test_run_cycle_agent_fail(orchestrator: Any) -> None:
    """Test cycle aborts if agent fails."""
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        orchestrator.agent.start.side_effect = Exception("Agent died")
        assert orchestrator.run_cycle("task", "branch") is False


def test_run_cycle_line_1_retry(orchestrator: Any) -> None:
    """Test retry loop on Line 1 failure."""
    # Fail once, then pass
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        with (
            patch.object(orchestrator, "_line_1_defense", side_effect=[False, True]),
            patch.object(orchestrator, "_line_2_defense", return_value=True),
        ):
            assert orchestrator.run_cycle("task", "branch") is True
            assert orchestrator.agent.start.call_count == 2


def test_run_cycle_line_2_retry(orchestrator: Any) -> None:
    """Test retry loop on Line 2 failure."""
    # Line 1 passes, Line 2 fails once then passes
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 5
        mock_get_settings.return_value = mock_settings

        with (
            patch.object(orchestrator, "_line_1_defense", return_value=True),
            patch.object(orchestrator, "_line_2_defense", side_effect=[False, True]),
        ):
            assert orchestrator.run_cycle("task", "branch") is True
            # Should retry, so start called twice
            assert orchestrator.agent.start.call_count == 2


def test_run_cycle_max_retries(orchestrator: Any) -> None:
    """Test max retries reached."""
    # Always fail Line 1
    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.max_retries = 2
        mock_get_settings.return_value = mock_settings

        with patch.object(orchestrator, "_line_1_defense", return_value=False):
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


def test_handle_ci_failure_summary(orchestrator: Any) -> None:
    """Test failure handler logs Janitor summary."""
    checks = [{"name": "test", "conclusion": "failure", "url": "http://fail"}]
    orchestrator.janitor.summarize_logs.return_value = "Summary Text"

    with patch("coreason_jules_automator.orchestrator.logger") as mock_logger:
        orchestrator._handle_ci_failure(checks)
        mock_logger.info.assert_any_call("Janitor Summary: Summary Text")


def test_orchestrator_line_1_defense_review_fail_coverage() -> None:
    """Explicit test to hit orchestrator.py line 70."""
    from coreason_jules_automator.orchestrator import Orchestrator

    with patch("coreason_jules_automator.orchestrator.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.extensions_enabled = ["code-review"]
        # mock_settings.max_retries = 1
        mock_get_settings.return_value = mock_settings

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
