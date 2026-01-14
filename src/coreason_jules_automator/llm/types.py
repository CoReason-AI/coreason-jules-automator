from dataclasses import dataclass
from typing import List, Dict

@dataclass
class LLMRequest:
    messages: List[Dict[str, str]]
    max_tokens: int

@dataclass
class LLMResponse:
    content: str
