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

import typer

from coreason_jules_automator.agent.jules import JulesAgent
from coreason_jules_automator.ci.git import GitInterface
from coreason_jules_automator.ci.github import GitHubInterface
from coreason_jules_automator.events import LoguruEmitter
from coreason_jules_automator.interfaces.gemini import GeminiInterface
from coreason_jules_automator.llm.factory import LLMFactory
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.orchestrator import Orchestrator
from coreason_jules_automator.strategies.local import LocalDefenseStrategy
from coreason_jules_automator.strategies.remote import RemoteDefenseStrategy
from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellExecutor

app = typer.Typer(
    name="vibe-runner",
    help="Hybrid Vibe Runner: Autonomous Orchestration Engine",
    add_completion=False,
)


@app.command(name="run")  # type: ignore[misc]
def run(
    task: str = typer.Argument(..., help="The task description for Jules."),
    branch: str = typer.Option(..., "--branch", "-b", help="The target branch name."),
) -> None:
    """
    Starts the Hybrid Vibe Runner cycle.
    """
    logger.info(f"Vibe Runner started. Task: {task}, Branch: {branch}")

    try:
        # Composition Root
        shell_executor = ShellExecutor()
        event_emitter = LoguruEmitter()

        gemini = GeminiInterface(shell_executor=shell_executor)
        git = GitInterface(shell_executor=shell_executor)
        github = GitHubInterface(shell_executor=shell_executor)

        llm_client = LLMFactory.get_client()
        janitor = JanitorService(llm_client=llm_client)

        local_strategy = LocalDefenseStrategy(gemini=gemini, event_emitter=event_emitter)
        remote_strategy = RemoteDefenseStrategy(
            github=github, janitor=janitor, git=git, event_emitter=event_emitter
        )

        agent = JulesAgent()

        orchestrator = Orchestrator(
            agent=agent,
            strategies=[local_strategy, remote_strategy],
            event_emitter=event_emitter,
        )

        success = orchestrator.run_cycle(task, branch)

        if success:
            logger.info("Cycle completed successfully.")
            sys.exit(0)
        else:
            logger.error("Cycle failed.")
            sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
