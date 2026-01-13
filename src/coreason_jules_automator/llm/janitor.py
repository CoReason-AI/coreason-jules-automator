import re
from typing import Optional

from coreason_jules_automator.llm.adapters import LLMClient
from coreason_jules_automator.utils.logger import logger


class JanitorService:
    """
    Business logic for cleaning commits and summarizing logs.
    """

    def __init__(self, llm_client: Optional[LLMClient]) -> None:
        self.client = llm_client

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
        prompt = (
            "You are a helpful assistant. "
            "Summarize the following CI failure logs into a concise 3-sentence hint for the developer:\n\n"
            f"{text[-2000:]}"  # Take last 2000 chars to avoid token limits
        )

        if self.client:
            try:
                return await self.client.complete(messages=[{"role": "user", "content": prompt}], max_tokens=150)

            except Exception as e:
                logger.error(f"LLM generation failed: {e}")

        return "Log summarization failed. Please check the logs directly."
