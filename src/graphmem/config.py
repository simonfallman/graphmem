"""Configuration management for GraphMem."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DBBackend(str, Enum):
    kuzu = "kuzu"
    neo4j = "neo4j"


class EmbedderProvider(str, Enum):
    openai = "openai"
    bedrock = "bedrock"
    local = "local"


class LLMProvider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    bedrock = "bedrock"
    ollama = "ollama"


def _default_db_path() -> str:
    return str(Path.home() / ".graphmem" / "db")


def _find_env_file() -> str | None:
    """Look for .env in CWD, then in ~/.graphmem/."""
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return str(cwd_env)
    home_env = Path.home() / ".graphmem" / ".env"
    if home_env.exists():
        return str(home_env)
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GRAPHMEM_",
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_backend: DBBackend = DBBackend.kuzu
    db_path: str = Field(default_factory=_default_db_path)

    # Neo4j (only used when db_backend=neo4j)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Provider selection
    embedder: EmbedderProvider = EmbedderProvider.openai
    llm: LLMProvider = LLMProvider.openai

    # OpenAI
    openai_api_key: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # AWS Bedrock
    aws_region: str = "us-east-1"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    bedrock_llm_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Local embeddings
    local_embed_model: str = "all-MiniLM-L6-v2"

    def resolve_db_path(self) -> str:
        """Expand ~ and ensure parent directory exists. Kuzu creates the DB dir itself."""
        path = Path(self.db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def get_openai_key(self) -> str:
        """Get OpenAI key from settings or env."""
        return self.openai_api_key or os.environ.get("OPENAI_API_KEY", "")

    def get_anthropic_key(self) -> str:
        """Get Anthropic key from settings or env."""
        return self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")


def load_settings() -> Settings:
    """Load settings from environment and .env file."""
    return Settings()
