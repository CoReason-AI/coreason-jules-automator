from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_jules_automator.llm.adapters import LlamaAdapter, OpenAIAdapter


@pytest.fixture
def mock_openai_client() -> Any:
    client = MagicMock()
    # Mocking AsyncOpenAI client structure
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def mock_llama_client() -> Any:
    client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_openai_adapter_complete(mock_openai_client: Any) -> None:
    adapter = OpenAIAdapter(mock_openai_client)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    result = await adapter.complete([{"role": "user", "content": "Hello"}])

    assert result == "Test response"
    mock_openai_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_llama_adapter_complete(mock_llama_client: Any) -> None:
    adapter = LlamaAdapter(mock_llama_client)
    mock_response = {"choices": [{"message": {"content": "Test response"}}]}
    mock_llama_client.create_chat_completion.return_value = mock_response

    result = await adapter.complete([{"role": "user", "content": "Hello"}])

    assert result == "Test response"
    mock_llama_client.create_chat_completion.assert_called_once()
