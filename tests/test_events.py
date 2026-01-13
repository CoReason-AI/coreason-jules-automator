from unittest.mock import patch

from coreason_jules_automator.events import AutomationEvent, EventType, LoguruEmitter


def test_automation_event_creation() -> None:
    event = AutomationEvent(type=EventType.CYCLE_START, message="Cycle started", payload={"task": "test"})
    assert event.type == EventType.CYCLE_START
    assert event.message == "Cycle started"
    assert event.payload == {"task": "test"}
    assert isinstance(event.timestamp, float)


def test_loguru_emitter_emit() -> None:
    emitter = LoguruEmitter()

    with patch("coreason_jules_automator.events.logger") as mock_logger:
        # Test Info level
        event = AutomationEvent(type=EventType.CYCLE_START, message="Cycle started", payload={"task": "test"})
        emitter.emit(event)
        mock_logger.info.assert_called_once()
        args, _ = mock_logger.info.call_args
        assert "[cycle_start]" in args[0]
        assert "Cycle started" in args[0]

        mock_logger.reset_mock()

        # Test Error level
        event_error = AutomationEvent(type=EventType.ERROR, message="Something failed", payload={"code": 1})
        emitter.emit(event_error)
        mock_logger.error.assert_called_once()
        args, _ = mock_logger.error.call_args
        assert "[error]" in args[0]

        mock_logger.reset_mock()

        # Test Check Result Fail
        event_fail = AutomationEvent(type=EventType.CHECK_RESULT, message="Check failed", payload={"status": "fail"})
        emitter.emit(event_fail)
        mock_logger.error.assert_called_once()

        mock_logger.reset_mock()

        # Test Check Result Pass
        event_pass = AutomationEvent(type=EventType.CHECK_RESULT, message="Check passed", payload={"status": "pass"})
        emitter.emit(event_pass)
        mock_logger.info.assert_called_once()
