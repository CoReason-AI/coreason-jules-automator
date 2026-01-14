from typing import Optional

from coreason_jules_automator.config import Settings
from coreason_jules_automator.llm.adapters import LlamaAdapter, LLMClient, OpenAIAdapter
from coreason_jules_automator.llm.model_manager import ModelManager
from coreason_jules_automator.utils.logger import logger


class LLMFactory:
    """Factory for creating LLM clients based on configuration."""

    def get_client(self, settings: Settings) -> Optional[LLMClient]:
        """
        Initializes the LLM client based on strategy and available keys.
        """
        strategy = settings.llm_strategy

        if strategy == "api":
            try:
                from openai import OpenAI
            except ImportError:
                logger.warning("openai package not installed. Falling back to local.")
                return self._initialize_local(settings)

            if settings.DEEPSEEK_API_KEY:
                logger.info("Initializing DeepSeek client")
                client = OpenAI(
                    api_key=settings.DEEPSEEK_API_KEY.get_secret_value(),
                    base_url="https://api.deepseek.com",
                )
                return OpenAIAdapter(client, model_name="deepseek-coder")
            elif settings.OPENAI_API_KEY:
                logger.info("Initializing OpenAI client")
                client = OpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
                return OpenAIAdapter(client)
            else:
                logger.warning("No valid API key found (OPENAI_API_KEY or DEEPSEEK_API_KEY). Falling back to local.")

        # Fallback to local
        return self._initialize_local(settings)

    def _initialize_local(self, settings: Settings) -> Optional[LLMClient]:
        """Initializes the local Llama client."""
        logger.info("Initializing Local Llama client")
        try:
            from llama_cpp import Llama

            model_manager = ModelManager()
            try:
                model_path = model_manager.ensure_model_downloaded()
            except RuntimeError as e:
                logger.warning(f"Could not download model: {e}")
                return None

            client = Llama(model_path=model_path, verbose=False)
            return LlamaAdapter(client)

        except ImportError as e:
            raise RuntimeError("llama-cpp-python not installed. Cannot use local LLM.") from e
        except Exception as e:
            # If model loading fails
            logger.warning(f"Failed to load local model: {e}")
            return None
