from typing import List, Optional

from coreason_jules_automator.async_api import (
    AsyncGeminiInterface,
    AsyncGitHubInterface,
    AsyncGitInterface,
    AsyncJulesAgent,
    AsyncLLMClient,
    AsyncOpenAIAdapter,
    AsyncOrchestrator,
    AsyncShellExecutor,
)
from coreason_jules_automator.config import Settings, get_settings
from coreason_jules_automator.domain.pipeline import DefenseStep
from coreason_jules_automator.events import CompositeEmitter, EventCollector, EventEmitter, LoguruEmitter
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.llm.prompts import PromptManager
from coreason_jules_automator.strategies.steps import (
    CIPollingStep,
    CodeReviewStep,
    GitPushStep,
    LogAnalysisStep,
    SecurityScanStep,
)
from coreason_jules_automator.utils.logger import logger


class PipelineBuilder:
    """Builder for the defense pipeline."""

    def __init__(
        self,
        settings: Settings,
        gemini: AsyncGeminiInterface,
        github: AsyncGitHubInterface,
        git: AsyncGitInterface,
        janitor: JanitorService,
        event_emitter: Optional[EventEmitter],
    ):
        self.settings = settings
        self.gemini = gemini
        self.github = github
        self.git = git
        self.janitor = janitor
        self.event_emitter = event_emitter

    def build(self) -> List[DefenseStep]:
        steps: List[DefenseStep] = []

        # 1. Security Scan
        if "security" in self.settings.extensions_enabled:
            steps.append(SecurityScanStep(settings=self.settings, gemini=self.gemini, event_emitter=self.event_emitter))

        # 2. Code Review
        if "code-review" in self.settings.extensions_enabled:
            steps.append(CodeReviewStep(settings=self.settings, gemini=self.gemini, event_emitter=self.event_emitter))

        # 3. Git Push
        steps.append(GitPushStep(janitor=self.janitor, git=self.git, event_emitter=self.event_emitter))

        # 4. CI Polling
        steps.append(CIPollingStep(github=self.github, event_emitter=self.event_emitter))

        # 5. Log Analysis
        steps.append(
            LogAnalysisStep(
                github=self.github,
                janitor=self.janitor,
                event_emitter=self.event_emitter,
            )
        )

        return steps


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
        self.janitor = JanitorService(prompt_manager=self.prompt_manager, llm_client=self.llm_client)

        # Pipeline Builder
        self.pipeline_builder = PipelineBuilder(
            settings=self.settings,
            gemini=self.gemini,
            github=self.github,
            git=self.git,
            janitor=self.janitor,
            event_emitter=self.composite_emitter,
        )
        self.pipeline = self.pipeline_builder.build()

        # Agent
        self.agent = AsyncJulesAgent(settings=self.settings)

        # Orchestrator
        self.orchestrator = AsyncOrchestrator(
            settings=self.settings,
            agent=self.agent,
            strategies=self.pipeline,
            event_emitter=self.composite_emitter,
            git_interface=self.git,
            janitor_service=self.janitor,
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
