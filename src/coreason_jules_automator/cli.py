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
from typing import Optional

import typer

from coreason_jules_automator.async_api import (
    AsyncGeminiInterface,
    AsyncGitHubInterface,
    AsyncGitInterface,
    AsyncJulesAgent,
    AsyncLLMClient,
    AsyncLocalDefenseStrategy,
    AsyncOpenAIAdapter,
    AsyncOrchestrator,
    AsyncRemoteDefenseStrategy,
    AsyncShellExecutor,
)
from coreason_jules_automator.config import get_settings, Settings
from coreason_jules_automator.events import CompositeEmitter, EventCollector, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.reporters.markdown import MarkdownReporter
from coreason_jules_automator.utils.logger import logger

app = typer.Typer(
    name="coreason-jules-automator",
    help="Coreason Jules Automator: Autonomous Orchestration Engine",
    add_completion=False,
)


def _get_async_llm_client(settings: Settings) -> Optional[AsyncLLMClient]:
    """
    Helper to instantiate an AsyncLLMClient based on settings.
    Mimics LLMFactory logic but for async.
    """
    if settings.llm_strategy == "api":
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed. Skipping Async LLM Client.")
            return None

        if settings.DEEPSEEK_API_KEY:
            logger.info("Initializing DeepSeek client (Async)")
            client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
                base_url="https://api.deepseek.com",
            )
            return AsyncOpenAIAdapter(client, model_name="deepseek-coder")
        elif settings.OPENAI_API_KEY:
            logger.info("Initializing OpenAI client (Async)")
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
            return AsyncOpenAIAdapter(client, model_name="gpt-3.5-turbo")
        else:
            logger.warning("No valid API key found. Skipping Async LLM Client.")
    else:
        logger.warning("Local LLM strategy not yet supported in Async CLI. Skipping Async LLM Client.")

    return None


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
        shell_executor = AsyncShellExecutor()

        log_emitter = LoguruEmitter()
        event_collector = EventCollector()
        composite_emitter = CompositeEmitter([log_emitter, event_collector])

        gemini = AsyncGeminiInterface(shell_executor=shell_executor)
        git = AsyncGitInterface(shell_executor=shell_executor)
        github = AsyncGitHubInterface(shell_executor=shell_executor)

        settings = get_settings()
        llm_client = _get_async_llm_client(settings)
        prompt_manager = PromptManager()
        janitor = JanitorService(prompt_manager=prompt_manager)

        local_strategy = AsyncLocalDefenseStrategy(gemini=gemini, event_emitter=composite_emitter)
        remote_strategy = AsyncRemoteDefenseStrategy(
            github=github,
            janitor=janitor,
            git=git,
            llm_client=llm_client,
            event_emitter=composite_emitter,
        )

        agent = AsyncJulesAgent()

        orchestrator = AsyncOrchestrator(
            agent=agent,
            strategies=[local_strategy, remote_strategy],
            event_emitter=composite_emitter,
            git_interface=git,
            janitor_service=janitor,
            llm_client=llm_client,
        )

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
        # Composition Root
        shell_executor = AsyncShellExecutor()

        log_emitter = LoguruEmitter()
        event_collector = EventCollector()
        composite_emitter = CompositeEmitter([log_emitter, event_collector])

        gemini = AsyncGeminiInterface(shell_executor=shell_executor)
        git = AsyncGitInterface(shell_executor=shell_executor)
        github = AsyncGitHubInterface(shell_executor=shell_executor)

        settings = get_settings()
        llm_client = _get_async_llm_client(settings)
        prompt_manager = PromptManager()
        janitor = JanitorService(prompt_manager=prompt_manager)

        local_strategy = AsyncLocalDefenseStrategy(gemini=gemini, event_emitter=composite_emitter)
        remote_strategy = AsyncRemoteDefenseStrategy(
            github=github,
            janitor=janitor,
            git=git,
            llm_client=llm_client,
            event_emitter=composite_emitter,
        )

        agent = AsyncJulesAgent()

        orchestrator = AsyncOrchestrator(
            agent=agent,
            strategies=[local_strategy, remote_strategy],
            event_emitter=composite_emitter,
            git_interface=git,
            janitor_service=janitor,
            llm_client=llm_client,
        )

        asyncio.run(orchestrator.run_campaign(task, base, count))
        logger.info("Campaign completed.")

    except Exception as e:
        logger.exception(f"Unexpected error in campaign: {e}")
        sys.exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
