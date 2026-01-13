from pathlib import Path

from coreason_jules_automator.events import AutomationEvent, EventType
from coreason_jules_automator.reporters.markdown import MarkdownReporter


def test_markdown_reporter_generates_report(tmp_path: Path) -> None:
    # Setup template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_file = template_dir / "report.md.j2"
    template_file.write_text("{{ task_name }} - {{ final_status }} - {{ checks_passed }}/{{ checks_count }}")

    reporter = MarkdownReporter(template_dir)

    events = [
        AutomationEvent(type=EventType.CYCLE_START, message="Start", timestamp=1000.0),
        AutomationEvent(type=EventType.PHASE_START, message="Phase 1", payload={"phase": "defense line 1"}),
        AutomationEvent(type=EventType.CHECK_RESULT, message="Lint", payload={"status": "pass"}, timestamp=1001.0),
        AutomationEvent(type=EventType.CHECK_RESULT, message="Security", payload={"status": "fail"}, timestamp=1002.0),
        AutomationEvent(
            type=EventType.CYCLE_START, message="End", timestamp=1003.0
        ),  # using cycle start as placeholder for end
    ]

    report = reporter.generate_report(events, "Task A", "main")

    assert "Task A - FAILURE - 1/2" in report


def test_markdown_reporter_renders_full_template(tmp_path: Path) -> None:
    # Copy actual template to tmp_path or rely on logic if we point to actual src
    # Here we will use the actual source directory to test integration with the real template

    template_dir = Path("src/coreason_jules_automator/templates")
    if not template_dir.exists():
        # Fallback if running in environment where src is different
        template_dir = Path("../src/coreason_jules_automator/templates")

    reporter = MarkdownReporter(template_dir)

    events = [
        AutomationEvent(type=EventType.CYCLE_START, message="Start", timestamp=1700000000.0),
        AutomationEvent(type=EventType.PHASE_START, message="Phase 1", payload={"phase": "defense line 1"}),
        AutomationEvent(type=EventType.CHECK_RESULT, message="Lint Check", payload={"status": "pass"}),
        AutomationEvent(type=EventType.PHASE_START, message="Phase 2", payload={"phase": "defense line 2"}),
        AutomationEvent(
            type=EventType.CHECK_RESULT, message="CI Build", payload={"status": "fail", "url": "http://ci"}
        ),
        AutomationEvent(type=EventType.AGENT_MESSAGE, message="I am fixing the build", timestamp=1700000010.0),
    ]

    report = reporter.generate_report(events, "Fix Build", "feature-1")

    assert "Certificate of Analysis" in report
    assert "**Task Name:** Fix Build" in report
    assert "**Status:** **FAILURE**" in report
    assert "Lint Check" in report
    assert "CI Build" in report
    assert "I am fixing the build" in report


def test_markdown_reporter_fallback_logic(tmp_path: Path) -> None:
    # Setup template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_file = template_dir / "report.md.j2"
    template_file.write_text("""
    Local: {% for c in local_checks %}{{ c.name }},{% endfor %}
    Remote: {% for c in remote_checks %}{{ c.name }},{% endfor %}
    """)

    reporter = MarkdownReporter(template_dir)

    events = [
        AutomationEvent(type=EventType.CYCLE_START, message="Start"),
        # No Phase Start
        AutomationEvent(type=EventType.CHECK_RESULT, message="Unknown Check", payload={"status": "pass"}),
        AutomationEvent(type=EventType.CHECK_RESULT, message="GitHub Action", payload={"status": "pass"}),
        AutomationEvent(type=EventType.CHECK_RESULT, message="Remote Build", payload={"status": "pass"}),
    ]

    report = reporter.generate_report(events, "Task B", "branch-b")

    assert "Local: Unknown Check," in report
    assert "Remote: GitHub Action,Remote Build," in report


def test_markdown_reporter_missing_cycle_start(tmp_path: Path) -> None:
    # Setup template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_file = template_dir / "report.md.j2"
    template_file.write_text("Duration: {{ duration }}")

    reporter = MarkdownReporter(template_dir)

    events = [
        AutomationEvent(type=EventType.CHECK_RESULT, message="Check", payload={"status": "pass"}, timestamp=1000.0),
        AutomationEvent(type=EventType.CHECK_RESULT, message="Check2", payload={"status": "pass"}, timestamp=1010.0),
    ]

    report = reporter.generate_report(events, "Task C", "branch-c")

    # 1010 - 1000 = 10 seconds
    assert "Duration: 0:00:10" in report
