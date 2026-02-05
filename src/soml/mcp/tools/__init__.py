"""
MCP Tools Package - Aggregates all tool modules.

This package provides smart, deterministic tools that can be used by:
- Internal CrewAI agents
- External MCP-compatible agents (Claude, Cursor, etc.)
- Direct API calls

Design Principles:
1. Smart Upserts: Each tool handles find-or-create + reconciliation internally
2. Deterministic Flow: Entity resolution logic is codified, not agent-decided
3. Idempotent Operations: Calling the same operation twice won't create duplicates
4. Minimal Agent Steps: Agent describes WHAT, tool handles HOW
"""

# Base types and utilities
from soml.mcp.tools.base import (
    UpsertResult,
    LinkResult,
    ProcessResult,
    _get_registry,
    _get_md_store,
    _get_graph_store,
    _get_resolver,
    _create_general_info_document,
    _append_to_general_info,
    _queue_embedding_generation,
    logger,
)

# Entity upsert tools
from soml.mcp.tools.entity import (
    upsert_person,
    upsert_project,
    upsert_goal,
    upsert_event,
    upsert_period,
    _create_person,
)

# Employment tools
from soml.mcp.tools.employment import (
    set_employment,
    end_employment,
    transition_coworker_relationship,
    find_coworkers,
)

# Relationship tools
from soml.mcp.tools.relationship import (
    link_entities,
    unlink_entities,
    get_entity_relationships,
    add_relationship,
    replace_relationship,
    RelationshipProposal,
    propose_relationship_changes,
    apply_relationship_proposal,
)

# Query tools
from soml.mcp.tools.query import (
    get_entity,
    search_entities,
    get_relationships,
    get_timeline,
    semantic_search,
    find_entities_by_name,
    get_entity_with_documents,
)

# Document tools
from soml.mcp.tools.document import (
    append_to_document,
    get_general_info,
    search_documents,
)

# Embedding tools
from soml.mcp.tools.embedding import (
    _generate_embedding_sync,
    _build_embedding_text,
    generate_and_store_embedding,
    generate_and_store_document_embedding,
    refresh_entity_embedding,
    refresh_all_embeddings,
)

# Intelligence tools
from soml.mcp.tools.intelligence import (
    detect_open_loops,
    find_duplicates,
    flag_for_review,
    clear_review_flag,
    get_items_needing_review,
    delete_entity,
)

# Batch processing
from soml.mcp.tools.batch import (
    process_extraction,
    _extract_employment_from_context,
    _is_organization_entity,
)


__all__ = [
    # Result types
    "UpsertResult",
    "LinkResult",
    "ProcessResult",
    # Entity operations
    "upsert_person",
    "upsert_project",
    "upsert_goal",
    "upsert_event",
    "upsert_period",
    # Employment operations
    "set_employment",
    "end_employment",
    "transition_coworker_relationship",
    "find_coworkers",
    # Relationship operations
    "link_entities",
    "unlink_entities",
    "get_entity_relationships",
    "add_relationship",
    "replace_relationship",
    "RelationshipProposal",
    "propose_relationship_changes",
    "apply_relationship_proposal",
    # Query operations
    "get_entity",
    "search_entities",
    "get_relationships",
    "get_timeline",
    "semantic_search",
    "find_entities_by_name",
    "get_entity_with_documents",
    # Document operations
    "append_to_document",
    "get_general_info",
    "search_documents",
    # Embedding operations
    "generate_and_store_embedding",
    "generate_and_store_document_embedding",
    "refresh_entity_embedding",
    "refresh_all_embeddings",
    # Intelligence operations
    "detect_open_loops",
    "find_duplicates",
    "flag_for_review",
    "clear_review_flag",
    "get_items_needing_review",
    "delete_entity",
    # Batch operations
    "process_extraction",
]

