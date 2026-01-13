import re
from typing import Optional

from coreason_jules_automator.llm.adapters import LLMClient
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.utils.logger import logger


class JanitorService:
    """
    Business logic for cleaning commits and summarizing logs.
    """

    def __init__(self, llm_client: Optional[LLMClient], prompt_manager: Optional[PromptManager] = None) -> None:
        self.client = llm_client
        self.prompt_manager = prompt_manager or PromptManager()

    def sanitize_commit(self, text: str) -> str:
        """
        Removes 'Co-authored-by' and bot signatures from commit messages.
        """
        # Remove Co-authored-by lines
        text = re.sub(r"^Co-authored-by:.*$", "", text, flags=re.MULTILINE)
        # Remove Signed-off-by lines
        text = re.sub(r"^Signed-off-by:.*$", "", text, flags=re.MULTILINE)
        # Remove empty lines at the end
        return text.strip()

    async def summarize_logs(self, text: str) -> str:
        """
        Converts detailed logs into a 3-sentence hint using the LLM.
        """
        try:
            prompt = self.prompt_manager.render("janitor_summarize.j2", logs=text[-2000:])
        except Exception as e:
            logger.error(f"Failed to render prompt: {e}")
            return "Log summarization failed due to template error."

        if self.client:
            try:
                return await self.client.complete(messages=[{"role": "user", "content": prompt}], max_tokens=150)

            except Exception as e:
                logger.error(f"LLM generation failed: {e}")

        return "Log summarization failed. Please check the logs directly."
