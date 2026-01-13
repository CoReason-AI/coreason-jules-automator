import re
from typing import Any, Optional

from coreason_jules_automator.utils.logger import logger


class JanitorService:
    """
    Business logic for cleaning commits and summarizing logs.
    """

    def __init__(self, llm_client: Optional[Any]) -> None:
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

    def summarize_logs(self, text: str) -> str:
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
                # Check if it's OpenAI client
                if hasattr(self.client, "chat"):
                    response = self.client.chat.completions.create(
                        model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}], max_tokens=150
                    )
                    return str(response.choices[0].message.content.strip())

                # Check if it's Llama client
                elif hasattr(self.client, "create_chat_completion"):
                    response = self.client.create_chat_completion(
                        messages=[{"role": "user", "content": prompt}], max_tokens=150
                    )
                    return str(response["choices"][0]["message"]["content"].strip())

            except Exception as e:
                logger.error(f"LLM generation failed: {e}")

        return "Log summarization failed. Please check the logs directly."
