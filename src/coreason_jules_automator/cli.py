# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import sys
from pathlib import Path

import typer

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.config import get_settings
from coreason_jules_automator.events import CompositeEmitter, EventCollector, LoguruEmitter
from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.llm.factory import LLMFactory
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.reporters.markdown import MarkdownReporter
from coreason_jules_automator.strategies.local import LocalDefenseStrategy
from coreason_jules_automator.strategies.remote import RemoteDefenseStrategy
from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellExecutor

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
        # Composition Root
        shell_executor = ShellExecutor()

        log_emitter = LoguruEmitter()
        event_collector = EventCollector()
        composite_emitter = CompositeEmitter([log_emitter, event_collector])

        gemini = GeminiInterface(shell_executor=shell_executor)
        git = GitInterface(shell_executor=shell_executor)
        github = GitHubInterface(shell_executor=shell_executor)

        settings = get_settings()
        llm_client = LLMFactory().get_client(settings)
        prompt_manager = PromptManager()
        janitor = JanitorService(llm_client=llm_client, prompt_manager=prompt_manager)

        local_strategy = LocalDefenseStrategy(gemini=gemini, event_emitter=composite_emitter)
        remote_strategy = RemoteDefenseStrategy(
            github=github, janitor=janitor, git=git, event_emitter=composite_emitter
        )

        agent = JulesAgent()

        orchestrator = Orchestrator(
            agent=agent,
            strategies=[local_strategy, remote_strategy],
            event_emitter=composite_emitter,
            git_interface=git,
            janitor_service=janitor,
        )

        success, _ = orchestrator.run_cycle(task, branch)

        # Generate Report
        try:
            reporter = MarkdownReporter(template_dir=Path(__file__).parent / "templates")
            report_content = reporter.generate_report(event_collector.get_events(), task, branch)

            # Simple filename generation
            # report_filename = f"CoA_{branch}_{int(datetime.datetime.now().timestamp())}.md"
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
    count: int = typer.Option(10, "--count", help="Number of iterations."),
) -> None:
    """
    Runs a multi-iteration campaign.
    """
    logger.info(f"Starting Campaign. Task: {task}, Base: {base}, Count: {count}")

    try:
        # Composition Root
        shell_executor = ShellExecutor()

        log_emitter = LoguruEmitter()
        event_collector = EventCollector()
        composite_emitter = CompositeEmitter([log_emitter, event_collector])

        gemini = GeminiInterface(shell_executor=shell_executor)
        git = GitInterface(shell_executor=shell_executor)
        github = GitHubInterface(shell_executor=shell_executor)

        settings = get_settings()
        llm_client = LLMFactory().get_client(settings)
        prompt_manager = PromptManager()
        janitor = JanitorService(llm_client=llm_client, prompt_manager=prompt_manager)

        local_strategy = LocalDefenseStrategy(gemini=gemini, event_emitter=composite_emitter)
        remote_strategy = RemoteDefenseStrategy(
            github=github, janitor=janitor, git=git, event_emitter=composite_emitter
        )

        agent = JulesAgent()

        orchestrator = Orchestrator(
            agent=agent,
            strategies=[local_strategy, remote_strategy],
            event_emitter=composite_emitter,
            git_interface=git,
            janitor_service=janitor,
        )

        orchestrator.run_campaign(task, base, count)
        logger.info("Campaign completed.")

    except Exception as e:
        logger.exception(f"Unexpected error in campaign: {e}")
        sys.exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
