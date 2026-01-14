import json
import re
from typing import Optional

from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.utils.logger import logger


class JanitorService:
    """
    Business logic for cleaning commits and summarizing logs.
    """

    def __init__(self, prompt_manager: Optional[PromptManager] = None) -> None:
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

    def build_summarize_request(self, log_text: str) -> LLMRequest:
        """
        Builds an LLMRequest to convert detailed logs into a 3-sentence hint.
        """
        prompt = self.prompt_manager.render("janitor_summarize.j2", logs=log_text[-2000:])
        return LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )

    def build_professionalize_request(self, raw_text: str) -> LLMRequest:
        """
        Builds an LLMRequest to rewrite the commit message to be professional.
        """
        # 1. Strip bot signatures
        cleaned_text = self.sanitize_commit(raw_text)

        prompt = self.prompt_manager.render("janitor_professionalize.j2", commit_text=cleaned_text)
        return LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )

    def parse_professionalize_response(self, original_text: str, llm_response_text: str) -> str:
        """
        Parses the LLM response to extract the professionalized commit message.
        Falls back to sanitized original text if parsing fails.
        """
        # Extract JSON object
        start = llm_response_text.find("{")
        end = llm_response_text.rfind("}")
        if start != -1 and end != -1:
            json_str = llm_response_text[start : end + 1]
            try:
                data = json.loads(json_str)
                if "commit_text" in data:
                    return str(data["commit_text"])
            except json.JSONDecodeError:
                logger.warning("JSON parse failed during professionalize response parsing.")
        else:
             logger.warning("No JSON braces found in response.")

        # Fallback
        return self.sanitize_commit(original_text)
