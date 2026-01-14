from dataclasses import dataclass
from typing import Dict, List


@dataclass
class LLMRequest:
    messages: List[Dict[str, str]]
    max_tokens: int


@dataclass
class LLMResponse:
    content: str
