from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from coreason_jules_automator.strategies.local import LocalDefenseStrategy
from coreason_jules_automator.strategies.base import DefenseResult


@pytest.fixture
def local_strategy():
    gemini = MagicMock()
    gemini.security_scan = AsyncMock(return_value="Scan passed")
    gemini.code_review = AsyncMock(return_value="Review passed")
    return LocalDefenseStrategy(gemini=gemini)


@pytest.mark.asyncio
async def test_execute_success(local_strategy):
    context = {"branch_name": "test"}
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]
        result = await local_strategy.execute(context)
        assert result.success
        local_strategy.gemini.security_scan.assert_called_once()
        local_strategy.gemini.code_review.assert_called_once()


@pytest.mark.asyncio
async def test_execute_failure(local_strategy):
    local_strategy.gemini.security_scan.side_effect = RuntimeError("Scan failed")
    context = {"branch_name": "test"}
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security"]
        result = await local_strategy.execute(context)
        assert not result.success
        assert "Scan failed" in result.message
