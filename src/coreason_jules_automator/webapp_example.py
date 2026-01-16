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

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

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
from coreason_jules_automator.utils.logger import logger

app = FastAPI()


class OrchestrationRequest(BaseModel):
    task: str
    branch: str


def _get_async_llm_client(settings: Settings) -> Optional[AsyncLLMClient]:
    """
    Helper to instantiate an AsyncLLMClient based on settings.
    """
    if settings.llm_strategy == "api":
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed. Skipping Async LLM Client.")
            return None

        if settings.DEEPSEEK_API_KEY:
            client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
                base_url="https://api.deepseek.com",
            )
            return AsyncOpenAIAdapter(client, model_name="deepseek-coder")
        elif settings.OPENAI_API_KEY:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
            return AsyncOpenAIAdapter(client, model_name="gpt-3.5-turbo")
    return None


async def run_orchestration_background(task: str, branch: str) -> None:
    logger.info(f"Starting background orchestration for task: {task} on branch: {branch}")
    try:
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

        success, msg = await orchestrator.run_cycle(task, branch)
        logger.info(f"Background orchestration completed. Success: {success}, Msg: {msg}")

    except Exception as e:
        logger.exception(f"Background orchestration failed: {e}")


@app.post("/start-campaign")
async def start_campaign(request: OrchestrationRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    background_tasks.add_task(run_orchestration_background, request.task, request.branch)
    return {"status": "Campaign started", "task": request.task, "branch": request.branch}
