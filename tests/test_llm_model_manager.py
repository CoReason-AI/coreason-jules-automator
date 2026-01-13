from unittest.mock import patch

import pytest
from coreason_jules_automator.llm.model_manager import ModelManager


def test_ensure_model_downloaded_failure() -> None:
    """Test ensure_model_downloaded raises RuntimeError on download failure."""
    with patch("coreason_jules_automator.llm.model_manager.hf_hub_download") as mock_download:
        mock_download.side_effect = Exception("Connection error")

        manager = ModelManager()
        with pytest.raises(RuntimeError, match="Failed to download model"):
            manager.ensure_model_downloaded()
