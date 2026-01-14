from typing import Any, Protocol, runtime_checkable

from coreason_jules_automator.llm.types import LLMRequest, LLMResponse


@runtime_checkable
class AsyncLLMClient(Protocol):
    """Protocol for Async LLM clients."""

    async def execute(self, request: LLMRequest) -> LLMResponse: ...


class AsyncOpenAIAdapter:
    """Adapter for OpenAI-compatible clients using Async I/O."""

    def __init__(self, client: Any, model_name: str) -> None:
        self.client = client
        self.model_name = model_name

    async def execute(self, request: LLMRequest) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=request.messages,
            max_tokens=request.max_tokens,
        )
        content = str(response.choices[0].message.content).strip()
        return LLMResponse(content=content)
