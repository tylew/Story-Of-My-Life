"""
Story of My Life (SOML)

A local-first knowledge agent for human memory, time, and meaning.
Personal temporal knowledge graph with Swarm-based multi-agent architecture.
"""

__version__ = "0.1.0"
__author__ = "SOML Team"

from soml.core.config import settings
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

