from typing import Any, Dict, List, Protocol, runtime_checkable

@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients."""
    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
        ...  # pragma: no cover

class OpenAIAdapter:
    """Adapter for OpenAI-compatible clients."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",  # This might need to be configurable, but for now strict implementation
            messages=messages,
            max_tokens=max_tokens
        )
        return str(response.choices[0].message.content).strip()

class LlamaAdapter:
    """Adapter for local Llama clients."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
        response = self.client.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens
        )
        return str(response["choices"][0]["message"]["content"]).strip()
