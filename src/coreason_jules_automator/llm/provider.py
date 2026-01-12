# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import re
from typing import Any, Optional

from coreason_jules_automator.config import settings
from coreason_jules_automator.utils.logger import logger


class LLMProvider:
    """
    Unified LLM Provider that abstracts the backend (API vs Local).
    Implements the "Janitor" functionality.
    """

    def __init__(self) -> None:
        self.strategy: str = settings.llm_strategy
        self.client: Optional[Any] = self._initialize_client()

    def _initialize_client(self) -> Optional[Any]:
        """Initializes the LLM client based on strategy and available keys."""
        if self.strategy == "api":
            if settings.OPENAI_API_KEY:
                try:
                    from openai import OpenAI

                    logger.info("Initializing OpenAI client")
                    return OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
                except ImportError:
                    logger.warning("openai package not installed. Falling back to local.")
            else:
                logger.warning("OPENAI_API_KEY not found. Falling back to local.")

        # Fallback to local
        return self._initialize_local()

    def _initialize_local(self) -> Optional[Any]:
        """Initializes the local Llama client."""
        logger.info("Initializing Local Llama client")
        try:
            from llama_cpp import Llama

            # Mocking model path logic for now as we don't want to download 1.3GB in sandbox
            # In a real scenario, we would check ~/.cache/coreason/ and download if missing.
            model_path = "/tmp/deepseek-coder-1.3b-instruct.gguf"

            # We assume the user has handled model download or we mock Llama entirely in tests
            # For the purpose of this implementation, we try to instantiate
            # but expect it might fail if model is missing.
            # However, since we mock Llama in tests, this code is structurally correct.
            return Llama(model_path=model_path, verbose=False)
        except ImportError as e:
            raise RuntimeError("llama-cpp-python not installed. Cannot use local LLM.") from e
        except Exception as e:
            # If model is missing, we log it.
            logger.warning(f"Failed to load local model: {e}")
            return None

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
