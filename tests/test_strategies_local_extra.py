from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from coreason_jules_automator.strategies.local import LocalDefenseStrategy

@pytest.fixture
def local_strategy() -> LocalDefenseStrategy:
    gemini = MagicMock()
    # Ensure security scan passes by default
    gemini.security_scan = AsyncMock(return_value="Scan passed")
    gemini.code_review = AsyncMock(return_value="Review passed")
    return LocalDefenseStrategy(gemini=gemini)

@pytest.mark.asyncio
async def test_execute_security_pass_review_fail(local_strategy: Any) -> None:
    """Test scenario where security scan passes but code review fails."""
    # Security scan is already passing by fixture
    # Make code review fail
    local_strategy.gemini.code_review.side_effect = RuntimeError("Code Review Error")

    context = {"branch_name": "test"}
    with patch("coreason_jules_automator.strategies.local.get_settings") as mock_settings:
        mock_settings.return_value.extensions_enabled = ["security", "code-review"]

        result = await local_strategy.execute(context)

        assert not result.success
        assert "Code Review failed" in result.message
        # Ensure security scan was run and passed (implied by execution flow reaching code review)
        local_strategy.gemini.security_scan.assert_called_once()
        local_strategy.gemini.code_review.assert_called_once()
