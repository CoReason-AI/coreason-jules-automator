import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Mock optional dependencies if needed, though patching in tests handles most cases
from coreason_jules_automator.webapp_example import _get_async_llm_client, app, run_orchestration_background

client = TestClient(app)


def test_start_campaign_endpoint() -> None:
    """Test the /start-campaign endpoint."""
    with patch("coreason_jules_automator.webapp_example.run_orchestration_background"):
        response = client.post(
            "/start-campaign",
            json={"task": "Test Task", "branch": "feature/test"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "status": "Campaign started",
            "task": "Test Task",
            "branch": "feature/test",
        }

    # Re-verify with explicit patch verification
    with patch("coreason_jules_automator.webapp_example.run_orchestration_background") as mock_bg_task:
        client.post(
            "/start-campaign",
            json={"task": "Test Task", "branch": "feature/test"},
        )
        mock_bg_task.assert_called_once_with("Test Task", "feature/test")


@pytest.mark.asyncio
async def test_run_orchestration_background() -> None:
    """Test the background orchestration logic."""
    with (
        patch("coreason_jules_automator.webapp_example.AsyncShellExecutor"),
        patch("coreason_jules_automator.webapp_example.AsyncGeminiInterface"),
        patch("coreason_jules_automator.webapp_example.AsyncGitInterface"),
        patch("coreason_jules_automator.webapp_example.AsyncGitHubInterface"),
        patch("coreason_jules_automator.webapp_example.get_settings"),
        patch("coreason_jules_automator.webapp_example._get_async_llm_client"),
        patch("coreason_jules_automator.webapp_example.PromptManager"),
        patch("coreason_jules_automator.webapp_example.JanitorService"),
        patch("coreason_jules_automator.webapp_example.SecurityScanStep"),
        patch("coreason_jules_automator.webapp_example.CodeReviewStep"),
        patch("coreason_jules_automator.webapp_example.GitPushStep"),
        patch("coreason_jules_automator.webapp_example.CIPollingStep"),
        patch("coreason_jules_automator.webapp_example.LogAnalysisStep"),
        patch("coreason_jules_automator.webapp_example.AsyncJulesAgent"),
        patch("coreason_jules_automator.webapp_example.AsyncOrchestrator") as MockOrchestrator,
    ):
        mock_orch_instance = MockOrchestrator.return_value
        # Use AsyncMock for the async run_cycle method
        mock_orch_instance.run_cycle = AsyncMock(return_value=(True, "Success"))

        await run_orchestration_background("Task", "Branch")

        mock_orch_instance.run_cycle.assert_called_once_with("Task", "Branch")


@pytest.mark.asyncio
async def test_run_orchestration_background_exception() -> None:
    """Test exception handling in background orchestration."""
    with (
        patch("coreason_jules_automator.webapp_example.AsyncShellExecutor"),
        patch("coreason_jules_automator.webapp_example.logger") as mock_logger,
        patch("coreason_jules_automator.webapp_example.AsyncGeminiInterface", side_effect=Exception("Setup Fail")),
    ):
        await run_orchestration_background("Task", "Branch")
        mock_logger.exception.assert_called_once()


def test_get_async_llm_client_openai_import_error() -> None:
    """Test helper when openai is not installed."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"

    with patch.dict(sys.modules, {"openai": None}):
        result = _get_async_llm_client(mock_settings)
        assert result is None


def test_get_async_llm_client_deepseek() -> None:
    """Test helper with DeepSeek key."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY.get_secret_value.return_value = "ds-key"
    mock_settings.OPENAI_API_KEY = None

    with patch("openai.AsyncOpenAI") as MockOpenAI:
        result = _get_async_llm_client(mock_settings)
        assert result is not None
        MockOpenAI.assert_called_with(api_key="ds-key", base_url="https://api.deepseek.com")


def test_get_async_llm_client_openai() -> None:
    """Test helper with OpenAI key."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY = None
    mock_settings.OPENAI_API_KEY.get_secret_value.return_value = "oa-key"

    with patch("openai.AsyncOpenAI") as MockOpenAI:
        result = _get_async_llm_client(mock_settings)
        assert result is not None
        MockOpenAI.assert_called_with(api_key="oa-key")


def test_get_async_llm_client_no_keys() -> None:
    """Test helper with API strategy but no keys."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "api"
    mock_settings.DEEPSEEK_API_KEY = None
    mock_settings.OPENAI_API_KEY = None

    # Ensure openai module exists
    with patch("openai.AsyncOpenAI"):
        result = _get_async_llm_client(mock_settings)
        assert result is None


def test_get_async_llm_client_local() -> None:
    """Test helper with local strategy."""
    mock_settings = MagicMock()
    mock_settings.llm_strategy = "local"

    result = _get_async_llm_client(mock_settings)
    assert result is None
