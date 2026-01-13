import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Protocol

from coreason_jules_automator.utils.logger import logger


class EventType(Enum):
    CYCLE_START = "cycle_start"
    PHASE_START = "phase_start"
    CHECK_RUNNING = "check_running"
    CHECK_RESULT = "check_result"
    AGENT_MESSAGE = "agent_message"
    ERROR = "error"


@dataclass
class AutomationEvent:
    type: EventType
    message: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)


class EventEmitter(Protocol):
    def emit(self, event: AutomationEvent) -> None:
        """Emits an automation event."""
        ...


class LoguruEmitter:
    """Adapter that logs events to Loguru."""

    def emit(self, event: AutomationEvent) -> None:
        if event.type == EventType.ERROR:
            logger.error(f"[{event.type.value}] {event.message} | {event.payload}")
        elif event.type == EventType.CHECK_RESULT:
            status = event.payload.get("status", "unknown")
            if status == "fail":
                logger.error(f"[{event.type.value}] {event.message} | {event.payload}")
            else:
                logger.info(f"[{event.type.value}] {event.message} | {event.payload}")
        else:
            logger.info(f"[{event.type.value}] {event.message} | {event.payload}")
