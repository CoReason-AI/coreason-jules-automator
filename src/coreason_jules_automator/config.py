# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import importlib.util
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings for the Hybrid Vibe Runner.
    Environment variables are prefixed with VIBE_.
    """

    model_config = SettingsConfigDict(
        env_prefix="VIBE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Tunable Settings
    llm_strategy: Literal["local", "api"] = Field(default="api", description="Strategy to use for LLM (local or api)")
    extensions_enabled: List[str] = Field(
        default_factory=lambda: ["security", "code-review"],
        description="List of enabled extensions",
    )
    max_retries: int = Field(default=5, description="Maximum number of retries")

    # Secrets (Validation Only)
    # Using SecretStr ensures they are not logged in repr
    GITHUB_TOKEN: SecretStr = Field(..., description="GitHub Token for gh CLI")
    GOOGLE_API_KEY: SecretStr = Field(..., description="Google API Key for Gemini")

    # Optional Secrets
    OPENAI_API_KEY: Optional[SecretStr] = Field(None, description="OpenAI API Key")
    DEEPSEEK_API_KEY: Optional[SecretStr] = Field(None, description="DeepSeek API Key")
    SSH_PRIVATE_KEY: Optional[SecretStr] = Field(None, description="SSH Private Key")

    @field_validator("GITHUB_TOKEN", "GOOGLE_API_KEY")
    @classmethod
    def validate_secrets(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value():
            raise ValueError("Secret must not be empty")
        return v

    @model_validator(mode="after")
    def validate_local_strategy(self) -> "Settings":
        if self.llm_strategy == "local":
            if not importlib.util.find_spec("llama_cpp"):
                raise ValueError(
                    "llm_strategy='local' requires 'llama-cpp-python' to be installed. "
                    "Install with 'poetry install -E local'."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of Settings.
    This allows for lazy loading and easier patching in tests.
    """
    return Settings()  # type: ignore[call-arg]
