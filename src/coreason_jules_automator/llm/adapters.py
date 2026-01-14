from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients."""

    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str: ...  # pragma: no cover


class OpenAIAdapter:
    """Adapter for OpenAI-compatible clients."""

    def __init__(self, client: Any, model_name: str = "gpt-3.5-turbo") -> None:
        self.client = client
        self.model_name = model_name

    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens,
        )
        return str(response.choices[0].message.content).strip()


class LlamaAdapter:
    """Adapter for local Llama clients."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def complete(self, messages: List[Dict[str, str]], max_tokens: int = 150) -> str:
        response = self.client.create_chat_completion(messages=messages, max_tokens=max_tokens)
        return str(response["choices"][0]["message"]["content"]).strip()
