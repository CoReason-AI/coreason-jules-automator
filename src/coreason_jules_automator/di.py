from typing import Optional

from coreason_jules_automator.async_api import (
    AsyncGeminiInterface,
    AsyncGitHubInterface,
    AsyncGitInterface,
    AsyncJulesAgent,
    AsyncLLMClient,
    AsyncLocalDefenseStrategy,
    AsyncOpenAIAdapter,
    AsyncOrchestrator,
    AsyncRemoteDefenseStrategy,
    AsyncShellExecutor,
)
from coreason_jules_automator.config import Settings, get_settings
from coreason_jules_automator.events import CompositeEmitter, EventCollector, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.utils.logger import logger

class Container:
    """
    Dependency Injection Container for Coreason Jules Automator.
    Wires up the application components.
    """
    def __init__(self) -> None:
        self.settings = get_settings()

        # Core Components
        self.shell_executor = AsyncShellExecutor()

        # Event System
        self.log_emitter = LoguruEmitter()
        self.event_collector = EventCollector()
        self.composite_emitter = CompositeEmitter([self.log_emitter, self.event_collector])

        # SCM Interfaces
        self.gemini = AsyncGeminiInterface(shell_executor=self.shell_executor)
        self.git = AsyncGitInterface(shell_executor=self.shell_executor)
        self.github = AsyncGitHubInterface(shell_executor=self.shell_executor)

        # Services
        self.llm_client = self._create_async_llm_client()
        self.prompt_manager = PromptManager()
        self.janitor = JanitorService(prompt_manager=self.prompt_manager)

        # Strategies
        self.local_strategy = AsyncLocalDefenseStrategy(
            gemini=self.gemini,
            event_emitter=self.composite_emitter
        )
        self.remote_strategy = AsyncRemoteDefenseStrategy(
            github=self.github,
            janitor=self.janitor,
            git=self.git,
            llm_client=self.llm_client,
            event_emitter=self.composite_emitter,
        )

        # Agent
        self.agent = AsyncJulesAgent(settings=self.settings)

        # Orchestrator
        self.orchestrator = AsyncOrchestrator(
            agent=self.agent,
            strategies=[self.local_strategy, self.remote_strategy],
            event_emitter=self.composite_emitter,
            git_interface=self.git,
            janitor_service=self.janitor,
            llm_client=self.llm_client,
        )

    def _create_async_llm_client(self) -> Optional[AsyncLLMClient]:
        """
        Helper to instantiate an AsyncLLMClient based on settings.
        """
        if self.settings.llm_strategy == "api":
            try:
                from openai import AsyncOpenAI
            except ImportError:
                logger.warning("openai package not installed. Skipping Async LLM Client.")
                return None

            if self.settings.DEEPSEEK_API_KEY:
                logger.info("Initializing DeepSeek client (Async)")
                client = AsyncOpenAI(
                    api_key=self.settings.DEEPSEEK_API_KEY.get_secret_value(),
                    base_url="https://api.deepseek.com",
                )
                return AsyncOpenAIAdapter(client, model_name="deepseek-coder")
            elif self.settings.OPENAI_API_KEY:
                logger.info("Initializing OpenAI client (Async)")
                client = AsyncOpenAI(api_key=self.settings.OPENAI_API_KEY.get_secret_value())
                return AsyncOpenAIAdapter(client, model_name="gpt-3.5-turbo")
            else:
                logger.warning("No valid API key found. Skipping Async LLM Client.")
        else:
            logger.warning("Local LLM strategy not yet supported in Async CLI. Skipping Async LLM Client.")

        return None
