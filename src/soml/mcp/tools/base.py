"""
MCP Tools - Base module with result types, singletons, and helpers.

This module provides the foundation for all MCP tools:
- Result dataclasses (UpsertResult, LinkResult, ProcessResult)
- Storage singletons (_get_registry, _get_md_store, etc.)
- General Info document helpers
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from soml.core.config import get_logger
from soml.core.types import (
    Document,
    DocumentType,
    EntityType,
    Source,
)
from soml.mcp.resolution import EntityResolver
from soml.storage.audit import AuditLog
from soml.storage.graph import GraphStore
from soml.storage.markdown import MarkdownStore
from soml.storage.registry import RegistryStore

logger = get_logger("mcp.tools")


# ============================================
# Result Types
# ============================================

@dataclass
class UpsertResult:
    """Result of an upsert operation."""
    
    action: Literal["created", "updated", "no_change", "needs_confirmation"]
    """What action was taken."""
    
    entity_id: str | None
    """ID of the entity (new or existing)."""
    
    entity: dict | None
    """The entity data."""
    
    changes: list[str] = field(default_factory=list)
    """What was changed (for updates)."""
    
    candidates: list[dict] | None = None
    """Candidate matches (if needs_confirmation)."""
    
    error: str | None = None
    """Error message if operation failed."""


@dataclass
class LinkResult:
    """Result of a link operation."""
    
    action: Literal["created", "exists", "updated", "failed"]
    """What action was taken."""
    
    relationship_id: str | None = None
    """ID of the relationship."""
    
    error: str | None = None


@dataclass
class ProcessResult:
    """Result of batch processing."""
    
    entities: list[UpsertResult] = field(default_factory=list)
    """Results for each entity."""
    
    relationships: list[LinkResult] = field(default_factory=list)
    """Results for each relationship."""
    
    needs_confirmation: list[dict] = field(default_factory=list)
    """Entities needing user confirmation."""


# ============================================
# Singletons for storage
# ============================================

_registry: RegistryStore | None = None
_md_store: MarkdownStore | None = None
_graph_store: GraphStore | None = None
_resolver: EntityResolver | None = None
_audit: AuditLog | None = None


def _get_registry() -> RegistryStore:
    global _registry
    if _registry is None:
        _registry = RegistryStore()
    return _registry


def _get_audit() -> AuditLog:
    global _audit
    if _audit is None:
        _audit = AuditLog(_get_registry())
    return _audit


def _get_md_store() -> MarkdownStore:
    global _md_store
    if _md_store is None:
        _md_store = MarkdownStore()
    return _md_store


def _get_graph_store() -> GraphStore:
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


def _get_resolver() -> EntityResolver:
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver


# ============================================
# General Info Document Helpers
# ============================================

def _create_general_info_document(
    entity_id: str,
    entity_type: EntityType,
    entity_name: str,
    initial_content: str,
    md_store: MarkdownStore,
    registry: RegistryStore,
) -> str | None:
    """
    Create a General Info document for an entity.
    
    Returns the document ID if created successfully.
    """
    doc = Document(
        id=uuid4(),
        title="General Info",  # Short title - slugifies to general-info.md
        document_type=DocumentType.GENERAL_INFO,
        content=initial_content,
        parent_entity_id=UUID(entity_id),
        parent_entity_type=entity_type,
        locked=True,  # LLM-only editable
        source=Source.AGENT,
        last_edited_by=Source.AGENT,
    )
    
    try:
        filepath = md_store.write_document(doc)
        
        # Index in registry
        registry.index(
            doc_id=str(doc.id),
            path=filepath,
            entity_type=EntityType.DOCUMENT,
            name=doc.title,
            checksum=md_store._compute_checksum(doc.content),
            content=doc.content,
            document_type="general_info",
            parent_entity_id=entity_id,
            parent_entity_type=entity_type.value if isinstance(entity_type, EntityType) else entity_type,
            locked=True,
        )
        
        logger.info(f"Created General Info document for {entity_name} ({entity_id})")
        return str(doc.id)
        
    except Exception as e:
        logger.error(f"Failed to create General Info document: {e}")
        return None


def _append_to_general_info(
    entity_id: str,
    entity_type: EntityType,
    entity_name: str,
    content: str,
    md_store: MarkdownStore,
    registry: RegistryStore,
) -> bool:
    """
    Append content to an entity's General Info document.
    Creates the document if it doesn't exist.
    
    Returns True if successful.
    """
    # Try to find existing General Info doc
    general_info = md_store.get_general_info_document(entity_id)
    
    if general_info:
        # Append to existing
        doc_id = general_info["metadata"].get("id")
        return md_store.append_to_document(doc_id, content, Source.AGENT)
    else:
        # Create new
        doc_id = _create_general_info_document(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_name,
            initial_content=content,
            md_store=md_store,
            registry=registry,
        )
        return doc_id is not None


def _queue_embedding_generation(entity_id: str) -> None:
    """Queue embedding generation for an entity (non-blocking)."""
    import threading
    from soml.mcp.tools.embedding import generate_and_store_embedding
    
    def _generate():
        try:
            generate_and_store_embedding(entity_id)
        except Exception as e:
            logger.warning(f"Failed to generate embedding for {entity_id}: {e}")
    
    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()


# Re-export for convenience
__all__ = [
    # Result types
    "UpsertResult",
    "LinkResult",
    "ProcessResult",
    # Singletons
    "_get_registry",
    "_get_md_store",
    "_get_graph_store",
    "_get_resolver",
    "_get_audit",
    # Helpers
    "_create_general_info_document",
    "_append_to_general_info",
    "_queue_embedding_generation",
    "logger",
]

