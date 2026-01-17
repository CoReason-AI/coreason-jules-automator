from typing import Optional

from pydantic import BaseModel, Field


class GitCommit(BaseModel):
    """Represents a git commit log/message."""

    message: str = Field(..., description="The raw commit message")


class PullRequestStatus(BaseModel):
    """Represents the status of a GitHub Pull Request check."""

    name: str = Field(..., description="Name of the check")
    status: str = Field(..., description="Status of the check (e.g. completed)")
    conclusion: Optional[str] = Field(None, description="Conclusion of the check (e.g. success, failure)")
    url: str = Field(..., description="URL to the check details")
