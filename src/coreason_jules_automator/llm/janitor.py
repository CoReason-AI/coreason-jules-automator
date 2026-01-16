import re
from typing import Optional

from pydantic import BaseModel, ValidationError

from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.utils.logger import logger


class CommitMessageResponse(BaseModel):
    commit_text: str


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
        return LLMRequest(messages=[{"role": "user", "content": prompt}], max_tokens=150)

    def build_professionalize_request(self, raw_text: str) -> LLMRequest:
        """
        Builds an LLMRequest to rewrite the commit message to be professional.
        """
        # 1. Strip bot signatures
        cleaned_text = self.sanitize_commit(raw_text)

        prompt = self.prompt_manager.render("janitor_professionalize.j2", commit_text=cleaned_text)
        return LLMRequest(messages=[{"role": "user", "content": prompt}], max_tokens=200)

    def parse_professionalize_response(self, original_text: str, llm_response_text: str) -> str:
        """
        Robustly parses LLM JSON response using Pydantic.
        Falls back to sanitized original text if parsing fails.
        """
        # Attempt to find JSON block if wrapped in markdown code blocks or just text
        json_match = re.search(r"\{.*\}", llm_response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else llm_response_text

        try:
            # Let Pydantic handle the validation
            data = CommitMessageResponse.model_validate_json(json_str)
            return data.commit_text
        except (ValidationError, ValueError):
            logger.warning("Failed to parse LLM JSON response. Falling back to sanitizer.")
            return self.sanitize_commit(original_text)
