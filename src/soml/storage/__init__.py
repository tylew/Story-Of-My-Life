"""
Storage Layer - Markdown, SQLite Registry, Neo4j Graph.

The storage hierarchy:
1. Markdown files → Canonical source of truth (human-readable, portable)
2. SQLite → Document registry, audit log, full-text search index
3. Neo4j → Graph relationships + vector embeddings (queryable cache)

All storage operations should go through these modules.
"""

from soml.storage.markdown import MarkdownStore
from soml.storage.registry import RegistryStore
from soml.storage.graph import GraphStore
from soml.storage.audit import AuditLog

__all__ = [
    "MarkdownStore",
    "RegistryStore",
    "GraphStore",
    "AuditLog",
]

