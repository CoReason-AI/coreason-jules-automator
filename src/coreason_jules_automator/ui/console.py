# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

from typing import Dict, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table

from coreason_jules_automator.events import AutomationEvent, EventType


class RichConsoleEmitter:
    """
    Renders automation events to a rich terminal UI.
    """

    def __init__(self) -> None:
        self.console = Console()
        self.checks: Dict[str, Dict[str, str]] = {}  # check_name -> {status, message}
        self.live: Optional[Live] = None
        self.current_check: Optional[str] = None

    def start(self) -> None:
        self.live = Live(self.generate_table(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop(self) -> None:
        if self.live:
            self.live.stop()

    def generate_table(self) -> Table:
        table = Table(title="Jules Automation Status", expand=True)
        table.add_column("Check/Step", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="dim")

        for name, data in self.checks.items():
            status = data.get("status", "running")
            msg = data.get("message", "")

            icon = "⏳"
            style = "yellow"
            if status == "pass" or status == "success":
                icon = "✅"
                style = "green"
            elif status == "fail" or status == "failed":
                icon = "❌"
                style = "red"
            elif status == "warn":
                icon = "⚠️"
                style = "yellow"

            table.add_row(name, icon, msg, style=style)

        return table

    def emit(self, event: AutomationEvent) -> None:
        if not self.live:
            return

        if event.type == EventType.CHECK_RUNNING:
            check_key = event.payload.get("check")
            if not check_key:
                # Heuristics for steps without explicit check ID
                if "Polling" in event.message:
                    check_key = "CI Polling"
                elif "Pushing Code" in event.message:
                    check_key = "Git Push"
                elif "Launching" in event.message:
                    check_key = "Session Launch"
                elif "Teleporting" in event.message:
                    check_key = "Code Sync"
                else:
                    check_key = event.message

            self.current_check = check_key
            self.checks[check_key] = {"status": "running", "message": event.message}
            self.live.update(self.generate_table())

        elif event.type == EventType.CHECK_RESULT:
            check_key = event.payload.get("check")
            if not check_key:
                # Heuristics to match result to running step
                if "CI checks" in event.message or "Polling" in event.message:
                    check_key = "CI Polling"
                elif "pushed" in event.message:
                    check_key = "Git Push"
                elif "Session Started" in event.message:
                    check_key = "Session Launch"
                elif "synced" in event.message:
                    check_key = "Code Sync"
                elif self.current_check:
                    check_key = self.current_check
                else:
                    check_key = "Result"

            status = event.payload.get("status", "pass")
            # Update the entry
            self.checks[check_key] = {"status": status, "message": event.message}
            self.live.update(self.generate_table())

        elif event.type == EventType.PHASE_START:
            # Maybe show a banner or just log?
            # We can add it as a row
            self.checks[event.message] = {"status": "info", "message": ""}
            self.live.update(self.generate_table())

        elif event.type == EventType.ERROR:
             self.checks["Error"] = {"status": "fail", "message": event.message}
             self.live.update(self.generate_table())
