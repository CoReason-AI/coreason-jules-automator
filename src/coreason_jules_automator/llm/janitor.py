from typing import Optional

from pydantic import BaseModel

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.utils.logger import logger


class CommitMessageResponse(BaseModel):
    commit_text: str


class SummaryResponse(BaseModel):
    summary: str


class JanitorService:
    """
    Business logic for cleaning commits and summarizing logs.
    Refactored to handle LLM interaction directly.
    """

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        llm_client: Optional[AsyncLLMClient] = None,
    ) -> None:
        self.prompt_manager = prompt_manager or PromptManager()
        self.llm_client = llm_client

    async def professionalize_commit(self, raw_text: str) -> str:
        """
        Rewrites the commit message to be professional using LLM.
        """
        if not self.llm_client:
            return raw_text.strip()

        # Render prompt
        prompt = self.prompt_manager.render("janitor_professionalize.j2", commit_text=raw_text)
        request = LLMRequest(messages=[{"role": "user", "content": prompt}], max_tokens=200)

        try:
            response = await self.llm_client.execute(request, response_model=CommitMessageResponse)
            return response.commit_text
        except Exception as e:
            logger.error(f"Professionalize commit failed: {e}")
            return raw_text.strip()

    async def summarize_logs(self, log_text: str) -> str:
        """
        Converts detailed logs into a 3-sentence hint using LLM.
        """
        if not self.llm_client:
            return "Log summarization unavailable (no LLM)."

        # Render prompt
        prompt = self.prompt_manager.render("janitor_summarize.j2", logs=log_text[-2000:])
        request = LLMRequest(messages=[{"role": "user", "content": prompt}], max_tokens=150)

        try:
            response = await self.llm_client.execute(request, response_model=SummaryResponse)
            return response.summary
        except Exception as e:
            logger.error(f"Log summarization failed: {e}")
            return "Log summarization failed."
