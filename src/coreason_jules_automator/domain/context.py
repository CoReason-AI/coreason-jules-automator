from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class OrchestrationContext(BaseModel):
    """
    Structured context for orchestration operations.
    Replaces generic Dict[str, Any].
    """
    task_id: str = Field(..., description="Unique identifier for the task.")
    branch_name: str = Field(..., description="The git branch name for the current operation.")
    session_id: str = Field(..., description="The session ID (SID) of the remote Jules agent.")

    # Allow extra fields if needed for extensibility, but warn if used excessively
    # frozen=True ensures immutability
    model_config = {"extra": "allow", "frozen": True}

class StrategyResult(BaseModel):
    """
    Standardized return type for defense strategies.
    Replaces DefenseResult dataclass.
    """
    success: bool = Field(..., description="Whether the strategy passed or failed.")
    message: str = Field(..., description="A descriptive message or feedback.")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured details about the result.")
