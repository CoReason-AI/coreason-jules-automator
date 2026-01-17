from typing import Any, Protocol, Type, TypeVar, runtime_checkable

from pydantic import BaseModel

from coreason_jules_automator.llm.types import LLMRequest

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class AsyncLLMClient(Protocol):
    """Protocol for Async LLM clients."""

    async def execute(self, request: LLMRequest, response_model: Type[T]) -> T: ...


class AsyncOpenAIAdapter:
    """Adapter for OpenAI-compatible clients using Async I/O."""

    def __init__(self, client: Any, model_name: str) -> None:
        self.client = client
        self.model_name = model_name

    async def execute(self, request: LLMRequest, response_model: Type[T]) -> T:
        response = await self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=request.messages,
            response_format=response_model,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
             raise ValueError("LLM failed to return structured output.")
        return parsed  # type: ignore[no-any-return]
