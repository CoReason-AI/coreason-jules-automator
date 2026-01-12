# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

"""
Configuration management for the Hybrid Vibe Runner.
"""

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration using environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="VIBE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Tunable Settings
    llm_strategy: Literal["local", "api"] = Field(
        default="api", description="LLM strategy: 'local' (Llama) or 'api' (OpenAI/DeepSeek)."
    )
    extensions_enabled: List[str] = Field(
        default=["security", "code-review"], description="List of enabled extensions."
    )
    max_retries: int = Field(default=5, description="Maximum number of retries for operations.")

    # Secrets (Validation Only)
    # Using uppercase to match existing code usage (settings.OPENAI_API_KEY)
    GITHUB_TOKEN: SecretStr = Field(..., validation_alias="GITHUB_TOKEN")
    GOOGLE_API_KEY: SecretStr = Field(..., validation_alias="GOOGLE_API_KEY")

    # Optional Secrets
    OPENAI_API_KEY: Optional[SecretStr] = Field(default=None, validation_alias="OPENAI_API_KEY")
    DEEPSEEK_API_KEY: Optional[SecretStr] = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    SSH_PRIVATE_KEY: Optional[SecretStr] = Field(default=None, validation_alias="SSH_PRIVATE_KEY")

    @field_validator("GITHUB_TOKEN", "GOOGLE_API_KEY")
    @classmethod
    def validate_secrets(cls, v: SecretStr, info: object) -> SecretStr:
        """
        Validate that critical secrets are present and not empty.
        """
        if not v or not v.get_secret_value():
            field_name = "unknown"
            if hasattr(info, "field_name"):
                field_name = info.field_name
            raise ValueError(f"{field_name} must be set and not empty.")
        return v

    @model_validator(mode="after")
    def validate_local_strategy(self) -> "Settings":
        """
        Ensure llama-cpp-python is installed if strategy is local.
        """
        if self.llm_strategy == "local":
            try:
                import llama_cpp  # noqa: F401
            except ImportError as e:
                # We raise a ValueError configuration error, not RuntimeError, as it's config validation
                raise ValueError(
                    "strategy='local' requires 'llama-cpp-python' to be installed. "
                    "Install with 'poetry install -E local' or pip install llama-cpp-python."
                ) from e
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings class.
    """
    # We allow instantiation to fail if environment variables are missing
    # This is handled by pydantic raising ValidationError
    # Mypy complains about missing args because it thinks we need to pass them,
    # but BaseSettings loads them from env.
    return Settings()  # type: ignore[call-arg]


# Alias for backward compatibility if needed
Config = Settings
