from unittest.mock import MagicMock
import pytest
from coreason_jules_automator.llm.adapters import OpenAIAdapter, LlamaAdapter

def test_openai_adapter_complete() -> None:
    """Test OpenAIAdapter.complete returns expected string."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "OpenAI response"

    adapter = OpenAIAdapter(mock_client)
    messages = [{"role": "user", "content": "Hello"}]
    result = adapter.complete(messages, max_tokens=100)

    assert result == "OpenAI response"
    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=100
    )

def test_llama_adapter_complete() -> None:
    """Test LlamaAdapter.complete returns expected string."""
    mock_client = MagicMock()
    mock_client.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "Llama response"}}]
    }

    adapter = LlamaAdapter(mock_client)
    messages = [{"role": "user", "content": "Hello"}]
    result = adapter.complete(messages, max_tokens=100)

    assert result == "Llama response"
    mock_client.create_chat_completion.assert_called_once_with(
        messages=messages,
        max_tokens=100
    )
