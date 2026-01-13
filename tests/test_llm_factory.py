from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from pydantic import SecretStr

from coreason_jules_automator.config import Settings
from coreason_jules_automator.llm.factory import LLMFactory


def test_get_client_api_openai_key() -> None:
    """Test initialization with OpenAI key."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = SecretStr("sk-test")
    mock_settings.DEEPSEEK_API_KEY = None

    with patch("openai.AsyncOpenAI") as mock_openai:
        factory = LLMFactory()
        factory.get_client(mock_settings)
        mock_openai.assert_called_with(api_key="sk-test")


def test_get_client_api_deepseek_key() -> None:
    """Test initialization with DeepSeek key."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.llm_strategy = "api"
    mock_settings.OPENAI_API_KEY = None
    mock_settings.DEEPSEEK_API_KEY = SecretStr("sk-deepseek")

    with patch("openai.AsyncOpenAI") as mock_openai:
        factory = LLMFactory()
        factory.get_client(mock_settings)
        mock_openai.assert_called_with(api_key="sk-deepseek", base_url="https://api.deepseek.com")
