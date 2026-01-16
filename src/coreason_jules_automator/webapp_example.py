# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

from typing import Dict

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

from coreason_jules_automator.container import OrchestratorContainer
from coreason_jules_automator.utils.logger import logger

app = FastAPI()


class OrchestrationRequest(BaseModel):
    task: str
    branch: str


async def run_orchestration_background(task: str, branch: str) -> None:
    logger.info(f"Starting background orchestration for task: {task} on branch: {branch}")
    try:
        container = OrchestratorContainer(capture_events=True)
        orchestrator = container.get_orchestrator()

        success, msg = await orchestrator.run_cycle(task, branch)
        logger.info(f"Background orchestration completed. Success: {success}, Msg: {msg}")

    except Exception as e:
        logger.exception(f"Background orchestration failed: {e}")


@app.post("/start-campaign")  # type: ignore[untyped-decorator]
async def start_campaign(request: OrchestrationRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    background_tasks.add_task(run_orchestration_background, request.task, request.branch)
    return {"status": "Campaign started", "task": request.task, "branch": request.branch}
