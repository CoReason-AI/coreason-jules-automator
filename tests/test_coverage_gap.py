import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.orchestrator import AsyncOrchestrator
from coreason_jules_automator.async_api.strategies import AsyncDefenseStrategy
from coreason_jules_automator.config import Settings
from coreason_jules_automator.di import Container

# --- Agent Tests ---


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COREASON_REPO_NAME", "dummy/repo")
    monkeypatch.setenv("COREASON_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("COREASON_GOOGLE_API_KEY", "dummy_key")


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        repo_name="dummy/repo",
        GITHUB_TOKEN="dummy_token",
        GOOGLE_API_KEY="dummy_key",
        max_retries=5,
    )


@pytest.mark.asyncio
async def test_agent_context_manager() -> None:
    """Test AsyncJulesAgent context manager to cover __aenter__ and __aexit__."""
    # We need to mock get_settings to avoid pydantic validation if env vars are not enough or if we want isolation
    with patch("coreason_jules_automator.async_api.agent.get_settings") as mock_settings:
        mock_settings.return_value.repo_name = "test/repo"

        agent = AsyncJulesAgent()
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()

        # We enter the context manager
        async with agent as a:
            assert a is agent
            # Simulate process creation by assigning it manually
            # This simulates that launch() was called and succeeded
            a.process = mock_process

        # Verify cleanup was called upon exit
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_awaited_once()
        assert agent.process is None


# --- Orchestrator Tests ---


@pytest.mark.asyncio
async def test_orchestrator_campaign_missing_deps(mock_settings: Settings) -> None:
    """Test run_campaign raises error when deps are missing (lines 171-173)."""
    mock_agent = MagicMock(spec=AsyncJulesAgent)

    # Test 1: Both missing
    orchestrator = AsyncOrchestrator(settings=mock_settings, agent=mock_agent, strategies=[])
    # git and janitor are None by default

    with pytest.raises(RuntimeError, match="GitInterface and JanitorService are required"):
        await orchestrator.run_campaign("task")

    # Test 2: Janitor missing
    mock_git = MagicMock()
    orchestrator = AsyncOrchestrator(settings=mock_settings, agent=mock_agent, strategies=[], git_interface=mock_git)
    with pytest.raises(RuntimeError, match="GitInterface and JanitorService are required"):
        await orchestrator.run_campaign("task")

    # Test 3: Git missing
    mock_janitor = MagicMock()
    orchestrator = AsyncOrchestrator(
        settings=mock_settings, agent=mock_agent, strategies=[], janitor_service=mock_janitor
    )
    with pytest.raises(RuntimeError, match="GitInterface and JanitorService are required"):
        await orchestrator.run_campaign("task")


@pytest.mark.asyncio
async def test_orchestrator_strategy_exception(mock_settings: Settings) -> None:
    """Test orchestrator handles exception in strategy execution (lines 171-173)."""
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.__aenter__ = AsyncMock(return_value=mock_agent)
    mock_agent.__aexit__ = AsyncMock(return_value=None)
    mock_agent.launch = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    # Use AsyncMock for strategy but make it raise exception
    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    # The code calls await strategy.execute(context=context)
    mock_strategy.execute = AsyncMock(side_effect=Exception("Strategy Boom"))

    mock_settings.max_retries = 1
    orchestrator = AsyncOrchestrator(settings=mock_settings, agent=mock_agent, strategies=[mock_strategy])

    success, feedback = await orchestrator.run_cycle("task", "branch")

    assert success is False
    assert "Strategy error: Strategy Boom" in feedback


# --- CLI Tests ---


def test_cli_campaign_exception() -> None:
    """Test cli campaign command exception handling (lines 92-94)."""
    from typer.testing import CliRunner

    from coreason_jules_automator.cli import app

    runner = CliRunner()

    # Patch Container to raise exception
    with patch("coreason_jules_automator.cli.Container", side_effect=Exception("Campaign Error")):
        result = runner.invoke(app, ["campaign", "task"])
        assert result.exit_code == 1
        # The exception is logged, so we check standard output/stderr usually but logger might intercept.
        # Just exit code 1 is enough to prove the exception block was entered.


# --- DI Tests ---


def test_di_container_llm_creation_deepseek() -> None:
    """Test Container LLM client creation with DeepSeek."""
    with patch("coreason_jules_automator.di.get_settings") as mock_settings:
        settings = MagicMock(spec=Settings)
        settings.llm_strategy = "api"
        settings.DEEPSEEK_API_KEY = MagicMock()
        settings.DEEPSEEK_API_KEY.get_secret_value.return_value = "ds-key"
        settings.OPENAI_API_KEY = None
        mock_settings.return_value = settings

        # Patch openai.AsyncOpenAI
        # We need to ensure openai is imported so we can patch it
        import openai

        with patch.object(openai, "AsyncOpenAI") as MockOpenAI:
            container = Container()
            assert container.llm_client is not None
            MockOpenAI.assert_called_with(api_key="ds-key", base_url="https://api.deepseek.com")


def test_di_container_llm_creation_openai() -> None:
    """Test Container LLM client creation with OpenAI."""
    with patch("coreason_jules_automator.di.get_settings") as mock_settings:
        settings = MagicMock(spec=Settings)
        settings.llm_strategy = "api"
        settings.DEEPSEEK_API_KEY = None
        settings.OPENAI_API_KEY = MagicMock()
        settings.OPENAI_API_KEY.get_secret_value.return_value = "oa-key"
        mock_settings.return_value = settings

        import openai

        with patch.object(openai, "AsyncOpenAI") as MockOpenAI:
            container = Container()
            assert container.llm_client is not None
            MockOpenAI.assert_called_with(api_key="oa-key")


def test_di_container_llm_creation_no_keys() -> None:
    """Test Container LLM client creation with no keys."""
    with patch("coreason_jules_automator.di.get_settings") as mock_settings:
        settings = MagicMock(spec=Settings)
        settings.llm_strategy = "api"
        settings.DEEPSEEK_API_KEY = None
        settings.OPENAI_API_KEY = None
        mock_settings.return_value = settings

        container = Container()
        assert container.llm_client is None


def test_di_container_llm_creation_local() -> None:
    """Test Container LLM client creation with local strategy."""
    with patch("coreason_jules_automator.di.get_settings") as mock_settings:
        settings = MagicMock(spec=Settings)
        settings.llm_strategy = "local"
        mock_settings.return_value = settings

        container = Container()
        assert container.llm_client is None


def test_di_container_llm_creation_import_error() -> None:
    """Test Container LLM client creation when openai is missing."""
    with patch("coreason_jules_automator.di.get_settings") as mock_settings:
        settings = MagicMock(spec=Settings)
        settings.llm_strategy = "api"
        mock_settings.return_value = settings

        # We need to simulate ImportError when importing openai.
        # Since 'openai' is likely installed and maybe cached, we can try to patch sys.modules.

        with patch.dict(sys.modules, {"openai": None}):
            # This causes 'import openai' to fail with ModuleNotFoundError (subclass of ImportError)
            # if it was set to None, OR we can remove it.
            # However, if we remove it, it tries to find it.
            # If we set it to None, standard import mechanism raises ModuleNotFoundError.
            # BUT the code uses `from openai import AsyncOpenAI`.

            # Let's verify if setting sys.modules["openai"] = None triggers ImportError on import.
            # In Python 3.12, setting sys.modules[name] = None causes "import name" to raise ModuleNotFoundError.
            # This satisfies "except ImportError".

            # But we must be careful if the module was already imported before.
            # Also `patch.dict` restores it afterwards.

            container = Container()
            assert container.llm_client is None
