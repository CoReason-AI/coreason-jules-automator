from typing import Dict, List
from pydantic import BaseModel


class LLMRequest(BaseModel):
    messages: List[Dict[str, str]]
    max_tokens: int


class LLMResponse(BaseModel):
    content: str
