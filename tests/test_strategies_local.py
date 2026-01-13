from unittest.mock import MagicMock, patch

import pytest
from coreason_jules_automator.strategies.local import LocalDefenseStrategy


@pytest.fixture
def mock_gemini() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_emitter() -> MagicMock:
    return MagicMock()


@pytest.fixture
def strategy(mock_gemini: MagicMock, mock_emitter: MagicMock) -> LocalDefenseStrategy:
    return LocalDefenseStrategy(gemini=mock_gemini, event_emitter=mock_emitter)


def test_execute_success(strategy: LocalDefenseStrategy, mock_gemini: MagicMock, mock_emitter: MagicMock) -> None:
    """Test successful execution of both security and code review."""
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]

        result = strategy.execute({})

        assert result.success is True
        assert result.message == "Local checks passed"
        mock_gemini.security_scan.assert_called_once()
        mock_gemini.code_review.assert_called_once()

        # Verify events
        # We expect: Phase Start, Security Running, Security Result, Review Running, Review Result
        assert mock_emitter.emit.call_count >= 5


def test_execute_security_fail(strategy: LocalDefenseStrategy, mock_gemini: MagicMock, mock_emitter: MagicMock) -> None:
    """Test failure in security scan."""
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]
        mock_gemini.security_scan.side_effect = RuntimeError("Security Issue")

        result = strategy.execute({})

        assert result.success is False
        assert "Security Scan failed: Security Issue" in result.message
        # Code review should still run (logic says errors.append, passed=False, then continues? No)
        # Looking at code:
        # if not passed: return ...
        # So code review is skipped if security scan fails.
        mock_gemini.code_review.assert_not_called()

        # Verify failure event
        calls = [args[0] for args, _ in mock_emitter.emit.call_args_list]
        fail_event = next(
            (e for e in calls if e.type.name == "CHECK_RESULT" and e.payload.get("status") == "fail"), None
        )
        assert fail_event is not None
        assert "Security Issue" in fail_event.payload["error"]


def test_execute_code_review_fail(strategy: LocalDefenseStrategy, mock_gemini: MagicMock) -> None:
    """Test failure in code review."""
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]
        mock_gemini.code_review.side_effect = RuntimeError("Code Style Issue")

        result = strategy.execute({})

        assert result.success is False
        assert "Code Review failed: Code Style Issue" in result.message


def test_execute_disabled_extensions(strategy: LocalDefenseStrategy, mock_gemini: MagicMock) -> None:
    """Test execution when extensions are disabled."""
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = []

        result = strategy.execute({})

        assert result.success is True
        mock_gemini.security_scan.assert_not_called()
        mock_gemini.code_review.assert_not_called()
