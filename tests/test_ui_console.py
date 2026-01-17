from unittest.mock import patch

from coreason_jules_automator.events import AutomationEvent, EventType
from coreason_jules_automator.ui.console import RichConsoleEmitter


def test_rich_console_emitter_init() -> None:
    emitter = RichConsoleEmitter()
    assert emitter.live is None
    assert emitter.current_check is None
    assert emitter.checks == {}


def test_rich_console_emitter_start_stop() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live") as MockLive:
        emitter.start()
        MockLive.assert_called_once()
        mock_live_instance = MockLive.return_value
        mock_live_instance.start.assert_called_once()

        emitter.stop()
        mock_live_instance.stop.assert_called_once()


def test_rich_console_emitter_stop_without_start() -> None:
    emitter = RichConsoleEmitter()
    # Should not raise exception
    emitter.stop()


def test_rich_console_emitter_generate_table() -> None:
    emitter = RichConsoleEmitter()
    emitter.checks["test_check"] = {"status": "pass", "message": "All good"}

    table = emitter.generate_table()
    assert table.title == "Jules Automation Status"
    # We can inspect rows but rich table structure is complex.
    # Just verify it doesn't crash and has content.
    assert table.row_count == 1


def test_rich_console_emitter_emit_without_live() -> None:
    """Ensure emit does nothing if start() wasn't called."""
    emitter = RichConsoleEmitter()
    event = AutomationEvent(type=EventType.CHECK_RUNNING, message="msg")
    # Should not raise error
    emitter.emit(event)
    assert emitter.checks == {}


def test_rich_console_emitter_emit_check_running() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live"):
        emitter.start()

        # Test explicit check payload
        event = AutomationEvent(type=EventType.CHECK_RUNNING, message="Running Scan", payload={"check": "security"})
        emitter.emit(event)

        assert emitter.current_check == "security"
        assert emitter.checks["security"]["status"] == "running"
        assert emitter.checks["security"]["message"] == "Running Scan"

        # Test heuristic: Polling
        event2 = AutomationEvent(type=EventType.CHECK_RUNNING, message="Polling CI Checks")
        emitter.emit(event2)
        assert emitter.checks["CI Polling"]["status"] == "running"

        # Test unknown
        event3 = AutomationEvent(type=EventType.CHECK_RUNNING, message="Something else")
        emitter.emit(event3)
        assert emitter.checks["Something else"]["status"] == "running"


def test_rich_console_emitter_emit_check_result() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live"):
        emitter.start()

        # Pre-set a running check
        emitter.current_check = "security"

        # Result for explicit check
        event = AutomationEvent(
            type=EventType.CHECK_RESULT, message="Scan passed", payload={"check": "security", "status": "pass"}
        )
        emitter.emit(event)
        assert emitter.checks["security"]["status"] == "pass"

        # Result using heuristic (current_check)
        event2 = AutomationEvent(type=EventType.CHECK_RESULT, message="Done")
        emitter.emit(event2)
        # Should update 'security' because it's current
        assert emitter.checks["security"]["message"] == "Done"

        # Reset current check to test fallback to "Result"
        emitter.current_check = None
        event3 = AutomationEvent(type=EventType.CHECK_RESULT, message="Mystery Result")
        emitter.emit(event3)
        assert emitter.checks["Result"]["message"] == "Mystery Result"


def test_rich_console_emitter_emit_phase_start() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live"):
        emitter.start()
        event = AutomationEvent(type=EventType.PHASE_START, message="Phase 1")
        emitter.emit(event)
        assert emitter.checks["Phase 1"]["status"] == "info"


def test_rich_console_emitter_emit_error() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live"):
        emitter.start()
        event = AutomationEvent(type=EventType.ERROR, message="Boom")
        emitter.emit(event)
        assert emitter.checks["Error"]["status"] == "fail"
        assert emitter.checks["Error"]["message"] == "Boom"


def test_rich_console_emitter_heuristics() -> None:
    emitter = RichConsoleEmitter()
    with patch("coreason_jules_automator.ui.console.Live"):
        emitter.start()

        # Test various heuristics in emit

        # CHECK_RUNNING heuristics
        events = [
            ("Pushing Code", "Git Push"),
            ("Launching Remote", "Session Launch"),
            ("Teleporting code", "Code Sync"),
            ("Unknown", "Unknown"),
        ]
        for msg, key in events:
            emitter.emit(AutomationEvent(type=EventType.CHECK_RUNNING, message=msg))
            assert key in emitter.checks

        # CHECK_RESULT heuristics
        events_res = [
            ("CI checks passed", "CI Polling"),
            ("Code pushed", "Git Push"),
            ("Session Started", "Session Launch"),
            ("Code synced", "Code Sync"),
        ]
        for msg, key in events_res:
            emitter.emit(AutomationEvent(type=EventType.CHECK_RESULT, message=msg))
            assert emitter.checks[key]["message"] == msg
