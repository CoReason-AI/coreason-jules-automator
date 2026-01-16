from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Mock optional dependencies if needed, though patching in tests handles most cases
from coreason_jules_automator.webapp_example import app, run_orchestration_background

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
    with patch("coreason_jules_automator.webapp_example.OrchestratorContainer") as MockContainer:
        mock_container = MockContainer.return_value
        mock_orch_instance = mock_container.get_orchestrator.return_value
        # Use AsyncMock for the async run_cycle method
        mock_orch_instance.run_cycle = AsyncMock(return_value=(True, "Success"))

        await run_orchestration_background("Task", "Branch")

        mock_orch_instance.run_cycle.assert_called_once_with("Task", "Branch")


@pytest.mark.asyncio
async def test_run_orchestration_background_exception() -> None:
    """Test exception handling in background orchestration."""
    with (
        patch("coreason_jules_automator.webapp_example.OrchestratorContainer", side_effect=Exception("Setup Fail")),
        patch("coreason_jules_automator.webapp_example.logger") as mock_logger,
    ):
        await run_orchestration_background("Task", "Branch")
        mock_logger.exception.assert_called_once()
