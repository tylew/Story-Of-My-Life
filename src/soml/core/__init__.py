"""
Core module - Configuration, types, context management, and LLM utilities.
"""

from soml.core.config import settings
from soml.core.context import SwarmContext
from soml.core.llm import call_llm, generate_embedding, generate_embeddings_batch, count_tokens
from soml.core.types import (
    Entity,
    EntityType,
    Event,
    Goal,
    Memory,
    Note,
    Person,
    Project,
    Relationship,
    RelationshipType,
)

__all__ = [
    "settings",
    "SwarmContext",
    "call_llm",
    "generate_embedding",
    "generate_embeddings_batch",
    "count_tokens",
    "Entity",
    "EntityType",
    "Event",
    "Goal",
    "Memory",
    "Note",
    "Person",
    "Project",
    "Relationship",
    "RelationshipType",
]

