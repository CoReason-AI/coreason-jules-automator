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
from pathlib import Path
from typing import Any, Optional

from huggingface_hub import hf_hub_download

from coreason_jules_automator.config import get_settings
from coreason_jules_automator.utils.logger import logger


class LLMProvider:
    """
    Unified LLM Provider that abstracts the backend (API vs Local).
    Implements the "Janitor" functionality.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.strategy: str = settings.llm_strategy
        self.client: Optional[Any] = self._initialize_client()

    def _initialize_client(self) -> Optional[Any]:
        """Initializes the LLM client based on strategy and available keys."""
        settings = get_settings()
        if self.strategy == "api":
            try:
                from openai import OpenAI
            except ImportError:
                logger.warning("openai package not installed. Falling back to local.")
                return self._initialize_local()

            if settings.OPENAI_API_KEY:
                logger.info("Initializing OpenAI client")
                return OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
            elif settings.DEEPSEEK_API_KEY:
                logger.info("Initializing DeepSeek client")
                return OpenAI(
                    api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
                    base_url="https://api.deepseek.com",
                )
            else:
                logger.warning("No valid API key found (OPENAI_API_KEY or DEEPSEEK_API_KEY). Falling back to local.")

        # Fallback to local
        return self._initialize_local()

    def _ensure_model_downloaded(self) -> str:
        """
        Ensures the local GGUF model is downloaded to ~/.cache/coreason/.
        Returns the path to the model file.
        """
        repo_id = "TheBloke/DeepSeek-Coder-1.3B-Instruct-GGUF"
        filename = "deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
        cache_dir = Path.home() / ".cache" / "coreason"

        logger.info(f"Ensuring model {repo_id}/{filename} is present in {cache_dir}")
        try:
            model_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                cache_dir=cache_dir,
                local_dir=cache_dir,  # Force download to specific dir for simplicity
                local_dir_use_symlinks=False,
            )
            # Explicitly cast to str for mypy, as hf_hub_download returns str | None in some versions or Any
            return str(model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download model: {e}") from e

    def _initialize_local(self) -> Optional[Any]:
        """Initializes the local Llama client."""
        logger.info("Initializing Local Llama client")
        try:
            from llama_cpp import Llama

            # Download or locate model
            try:
                model_path = self._ensure_model_downloaded()
            except RuntimeError as e:
                logger.warning(f"Could not download model: {e}")
                return None

            return Llama(model_path=model_path, verbose=False)

        except ImportError as e:
            raise RuntimeError("llama-cpp-python not installed. Cannot use local LLM.") from e
        except Exception as e:
            # If model loading fails
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
