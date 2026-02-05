"""
Configuration management for Story of My Life.

Uses pydantic-settings for environment variable binding.
All settings can be overridden via environment variables with SOML_ prefix.
"""

import logging
import sys
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable binding."""
    
    model_config = SettingsConfigDict(
        env_prefix="SOML_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # ==========================================
    # Data Storage
    # ==========================================
    data_dir: Path = Path.home() / "story-of-my-life"
    """Root directory for all markdown documents."""
    
    # ==========================================
    # Neo4j Configuration
    # ==========================================
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "somlpassword123"
    
    # ==========================================
    # LLM Configuration
    # ==========================================
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_llm: Literal["openai", "anthropic"] = "openai"
    
    # OpenAI models
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Anthropic models
    anthropic_model: str = "claude-sonnet-4-20250514"
    
    # ==========================================
    # Embedding Configuration
    # ==========================================
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100
    
    # ==========================================
    # Agent Configuration
    # ==========================================
    relationship_decay_days: int = 14
    """Days without interaction before relationship flagged as quiet."""
    
    project_decay_days: int = 7
    """Days without activity before project flagged as stalled."""
    
    goal_decay_days: int = 30
    """Days without progress before goal flagged as stalled."""
    
    # ==========================================
    # Document Settings
    # ==========================================
    max_document_lines: int = 500
    """Lines threshold for triggering hierarchical document split."""
    
    # ==========================================
    # MCP Server
    # ==========================================
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8765
    
    # ==========================================
    # Logging
    # ==========================================
    log_level: str = "INFO"
    log_file: Path | None = None
    
    # ==========================================
    # Computed Properties
    # ==========================================
    @property
    def people_dir(self) -> Path:
        return self.data_dir / "people"
    
    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"
    
    @property
    def goals_dir(self) -> Path:
        return self.data_dir / "goals"
    
    @property
    def events_dir(self) -> Path:
        return self.data_dir / "events"
    
    @property
    def notes_dir(self) -> Path:
        return self.data_dir / "notes"
    
    @property
    def memories_dir(self) -> Path:
        return self.data_dir / "memories"
    
    @property
    def deleted_dir(self) -> Path:
        return self.data_dir / ".deleted"
    
    @property
    def index_dir(self) -> Path:
        return self.data_dir / ".index"
    
    @property
    def registry_path(self) -> Path:
        return self.index_dir / "registry.sqlite"
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for directory in [
            self.people_dir,
            self.projects_dir,
            self.goals_dir,
            self.events_dir,
            self.notes_dir,
            self.memories_dir,
            self.deleted_dir,
            self.index_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


def setup_logging(level: str | None = None) -> None:
    """Configure application logging."""
    log_level = level or settings.log_level
    
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]
    
    if settings.log_file:
        handlers.append(logging.FileHandler(settings.log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=handlers,
    )
    
    # Quiet noisy libraries
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(f"soml.{name}")

