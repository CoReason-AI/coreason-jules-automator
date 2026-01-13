import datetime
from pathlib import Path
from typing import List, Dict, Any

from jinja2 import Environment, FileSystemLoader

from coreason_jules_automator.events import AutomationEvent, EventType


class MarkdownReporter:
    def __init__(self, template_dir: str | Path) -> None:
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.template = self.env.get_template("report.md.j2")

    def generate_report(self, events: List[AutomationEvent], task_name: str, branch_name: str) -> str:
        # Pre-process events

        start_time = None
        end_time = None

        local_checks = []
        remote_checks = []
        agent_messages = []

        checks_passed = 0
        checks_failed = 0

        # Simple heuristic to determine which phase a check belongs to
        # Assuming phases are emitted. If not, we might need to rely on event content or order.
        # But for now, let's categorize based on message content or assume a simple split.
        # Ideally, PHASE_START events would guide us.

        current_phase = "unknown"

        for event in events:
            if event.type == EventType.CYCLE_START:
                start_time = event.timestamp

            if event.type == EventType.PHASE_START:
                # payload might contain phase name
                current_phase = event.payload.get("phase", "unknown").lower()

            if event.type == EventType.CHECK_RESULT:
                status = event.payload.get("status", "unknown")
                check_item = {
                    "name": event.message,
                    "status": status,
                    "message": str(event.payload)
                }

                if status == "pass":
                    checks_passed += 1
                elif status == "fail":
                    checks_failed += 1

                # Assign to phase
                if "local" in current_phase or "defense line 1" in current_phase:
                    local_checks.append(check_item)
                elif "remote" in current_phase or "defense line 2" in current_phase:
                    remote_checks.append(check_item)
                else:
                    # Fallback based on message content if phase tracking failed
                    if "GitHub" in event.message or "Remote" in event.message:
                         remote_checks.append(check_item)
                    else:
                         local_checks.append(check_item)

            if event.type == EventType.AGENT_MESSAGE:
                 agent_messages.append({
                     "timestamp": datetime.datetime.fromtimestamp(event.timestamp, datetime.UTC).strftime("%H:%M:%S"),
                     "content": event.message
                 })

        if not start_time:
            start_time = events[0].timestamp if events else 0

        end_time = events[-1].timestamp if events else start_time
        duration_seconds = end_time - start_time
        duration = str(datetime.timedelta(seconds=int(duration_seconds)))

        final_status = "SUCCESS" if checks_failed == 0 else "FAILURE"

        context = {
            "task_name": task_name,
            "branch_name": branch_name,
            "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "final_status": final_status,
            "duration": duration,
            "checks_count": checks_passed + checks_failed,
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "local_checks": local_checks,
            "remote_checks": remote_checks,
            "agent_messages": agent_messages
        }

        return self.template.render(context)
