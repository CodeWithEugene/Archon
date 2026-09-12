"""Typed configuration loaded from environment variables and an optional .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ULTRA_DEFAULT = "nvidia/Nemotron-3-Ultra-550b-a55b"
SUPER_DEFAULT = "nvidia/nemotron-3-super-120b-a12b"
NANO_DEFAULT = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Nebius
    nebius_api_key: str = Field(default="", alias="NEBIUS_API_KEY")
    nebius_base_url: str = Field(default="https://api.tokenfactory.nebius.com/v1/", alias="NEBIUS_BASE_URL")
    nebius_sandbox_url: str = Field(
        default="https://api.tokenfactory.nebius.com/sandboxes/", alias="NEBIUS_SANDBOX_URL"
    )
    nebius_project_id: str = Field(default="", alias="NEBIUS_PROJECT_ID")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="archon", alias="LANGSMITH_PROJECT")
    langsmith_endpoint: str = Field(default="", alias="LANGSMITH_ENDPOINT")

    # Behaviour
    env: Literal["development", "production"] = Field(default="development", alias="ARCHON_ENV")
    llm_backend: Literal["nebius", "fake"] = Field(default="nebius", alias="ARCHON_LLM_BACKEND")
    sandbox_backend: Literal["contree", "local", "fake"] = Field(default="contree", alias="ARCHON_SANDBOX_BACKEND")
    demo_token: str = Field(default="", alias="ARCHON_DEMO_TOKEN")
    max_mission_usd: float = Field(default=3.0, alias="ARCHON_MAX_MISSION_USD")
    max_iterations: int = Field(default=5, alias="ARCHON_MAX_ITERATIONS")
    candidates_per_iteration: int = Field(default=2, alias="ARCHON_CANDIDATES_PER_ITERATION")
    command_timeout_s: int = Field(default=900, alias="ARCHON_COMMAND_TIMEOUT_S")
    tavily_timeout_s: float = Field(default=10.0, alias="ARCHON_TAVILY_TIMEOUT_S")
    db_path: Path = Field(default=Path("./archon.db"), alias="ARCHON_DB_PATH")
    recordings_dir: Path = Field(default=Path("./tests/golden/recordings"), alias="ARCHON_RECORDINGS_DIR")
    cors_origins: str = Field(default="http://localhost:3000", alias="ARCHON_CORS_ORIGINS")
    allow_local_repos: bool = Field(default=False, alias="ARCHON_ALLOW_LOCAL_REPOS")
    pricing_path: Path = Field(default=Path("./pricing.json"), alias="ARCHON_PRICING_PATH")
    swe_instances_path: Path = Field(default=Path("./tests/golden/instances.json"), alias="ARCHON_SWE_INSTANCES")
    base_image: str = Field(default="python:3.12-slim", alias="ARCHON_BASE_IMAGE")
    narrate_with_super: bool = Field(default=False, alias="ARCHON_NARRATE_WITH_SUPER")

    # Models
    ultra_model: str = Field(default=ULTRA_DEFAULT, alias="ARCHON_ULTRA_MODEL")
    super_model: str = Field(default=SUPER_DEFAULT, alias="ARCHON_SUPER_MODEL")
    nano_model: str = Field(default=NANO_DEFAULT, alias="ARCHON_NANO_MODEL")

    @field_validator("max_iterations")
    @classmethod
    def _iterations_bounds(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("ARCHON_MAX_ITERATIONS must be between 1 and 10")
        return v

    @field_validator("candidates_per_iteration")
    @classmethod
    def _candidates_bounds(cls, v: int) -> int:
        if not 1 <= v <= 4:
            raise ValueError("ARCHON_CANDIDATES_PER_ITERATION must be between 1 and 4")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def live_mode_requires_token(self) -> bool:
        return bool(self.demo_token)

    def validate_for_runtime(self) -> list[str]:
        """Return human-readable problems that would prevent the configured backends from working."""
        problems: list[str] = []
        if self.llm_backend == "nebius" and not self.nebius_api_key:
            problems.append("NEBIUS_API_KEY is empty but ARCHON_LLM_BACKEND=nebius")
        if self.sandbox_backend == "contree":
            if not self.nebius_api_key:
                problems.append("NEBIUS_API_KEY is empty but ARCHON_SANDBOX_BACKEND=contree")
            if not self.nebius_project_id:
                problems.append("NEBIUS_PROJECT_ID is empty but ARCHON_SANDBOX_BACKEND=contree")
        if self.sandbox_backend == "local" and self.env == "production":
            problems.append("ARCHON_SANDBOX_BACKEND=local is not allowed in production")
        if self.env == "production" and not self.demo_token:
            problems.append("ARCHON_DEMO_TOKEN must be set in production")
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
