"""Application settings loaded from environment / .env.

Single source of truth for all configuration. Every other module reads from `settings`,
never directly from os.environ. Makes testing trivial (override the model) and prevents
the "constant defined in two places" class of bug.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"
    AZURE_OPENAI_DEPLOYMENT_CHAT: str = "gpt-4o"
    AZURE_OPENAI_DEPLOYMENT_EMBED: str = "text-embedding-3-small"

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    PROMPT_CACHE_TTL_SECONDS: int = 300
    LANGFUSE_PROMPT_AUTOSYNC: bool = False

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_POLICY: str = "refund_policy_v1"

    # Durable state
    SQLITE_PATH: str = "data/state.db"

    # Behavior
    AGENT_LOG_LEVEL: str = "INFO"
    AUTO_APPROVAL_CAP_STANDARD_USD: float = 200.0
    AUTO_APPROVAL_CAP_VIP_USD: float = 500.0
    COMPACTION_TOKEN_THRESHOLD: int = 4000
    TOOL_TIMEOUT_SECONDS: float = 10.0
    TOOL_MAX_RETRIES: int = 2

    # Frontend
    GRADIO_SERVER_NAME: str = "0.0.0.0"
    GRADIO_SERVER_PORT: int = 7860

    # Paths (computed)
    POLICY_DOC_PATH: Path = Field(default=REPO_ROOT / "data" / "policy" / "refund_policy_v1.md")
    CUSTOMERS_PATH: Path = Field(default=REPO_ROOT / "data" / "crm" / "customers.json")
    ORDERS_PATH: Path = Field(default=REPO_ROOT / "data" / "crm" / "orders.json")
    SKILLS_DIR: Path = Field(default=REPO_ROOT / "skills")
    PROMPTS_DIR: Path = Field(default=REPO_ROOT / "prompts")
    INCIDENTS_DIR: Path = Field(default=REPO_ROOT / "data" / "incidents")
    AGENTIC_MD_PATH: Path = Field(default=REPO_ROOT / "agentic.md")

    @property
    def sqlite_full_path(self) -> Path:
        return REPO_ROOT / self.SQLITE_PATH

    @property
    def azure_configured(self) -> bool:
        return bool(self.AZURE_OPENAI_API_KEY and self.AZURE_OPENAI_ENDPOINT)

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY)


settings = Settings()
