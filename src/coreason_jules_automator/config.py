from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # type: ignore
    """
    Application settings loaded from environment variables with VIBE_ prefix.
    """

    model_config = SettingsConfigDict(env_prefix="VIBE_", env_file=".env", env_file_encoding="utf-8")

    llm_strategy: Literal["local", "api"] = "api"
    extensions_enabled: List[str] = ["security", "code-review"]
    max_retries: int = 5


settings = Settings()
