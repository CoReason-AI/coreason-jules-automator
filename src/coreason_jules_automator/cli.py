# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import asyncio
import sys
from pathlib import Path

import typer

from coreason_jules_automator.di import Container
from coreason_jules_automator.reporters.markdown import MarkdownReporter
from coreason_jules_automator.utils.logger import logger

app = typer.Typer(
    name="coreason-jules-automator",
    help="Coreason Jules Automator: Autonomous Orchestration Engine",
    add_completion=False,
)


@app.command(name="run")
def run(
    task: str = typer.Argument(..., help="The task description for Jules."),
    branch: str = typer.Option(..., "--branch", "-b", help="The target branch name."),
) -> None:
    """
    Starts the Coreason Jules Automator cycle.
    """
    logger.info(f"Coreason Jules Automator started. Task: {task}, Branch: {branch}")

    try:
        # Dependency Injection
        container = Container()
        orchestrator = container.orchestrator
        event_collector = container.event_collector

        success, _ = asyncio.run(orchestrator.run_cycle(task, branch))

        # Generate Report
        try:
            reporter = MarkdownReporter(template_dir=Path(__file__).parent / "templates")
            report_content = reporter.generate_report(event_collector.get_events(), task, branch)

            # Per MVP instruction:
            report_filename = "REPORT.md"

            with open(report_filename, "w") as f:
                f.write(report_content)

            logger.info(f"Certificate of Analysis generated: {report_filename}")
        except Exception as report_err:
            logger.error(f"Failed to generate report: {report_err}")

        if success:
            logger.info("Cycle completed successfully.")
            sys.exit(0)
        else:
            logger.error("Cycle failed.")
            sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


@app.command(name="campaign")
def campaign(
    task: str = typer.Argument(..., help="The task description for the campaign."),
    base: str = typer.Option("develop", "--base", help="Base branch for the campaign."),
    count: int = typer.Option(0, "--count", help="Number of iterations. 0 for Infinite Mode."),
) -> None:
    """
    Runs a multi-iteration campaign.
    """
    logger.info(f"Starting Campaign. Task: {task}, Base: {base}, Count: {count}")

    try:
        # Dependency Injection
        container = Container()
        orchestrator = container.orchestrator

        asyncio.run(orchestrator.run_campaign(task, base, count))
        logger.info("Campaign completed.")

    except Exception as e:
        logger.exception(f"Unexpected error in campaign: {e}")
        sys.exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
