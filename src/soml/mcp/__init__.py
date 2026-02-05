"""
MCP Tools Package - Unified tool interface for SOML.

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

# Import all tools from the modular tools package
from soml.mcp.tools import (
    # Result types
    UpsertResult,
    LinkResult,
    ProcessResult,
    # Entity upsert tools
    upsert_person,
    upsert_project,
    upsert_goal,
    upsert_event,
    upsert_period,
    # Employment tools
    set_employment,
    end_employment,
    transition_coworker_relationship,
    find_coworkers,
    # Relationship tools
    link_entities,
    unlink_entities,
    get_entity_relationships,
    add_relationship,
    replace_relationship,
    RelationshipProposal,
    propose_relationship_changes,
    apply_relationship_proposal,
    # Query tools
    get_entity,
    search_entities,
    get_relationships,
    get_timeline,
    semantic_search,
    find_entities_by_name,
    get_entity_with_documents,
    # Document tools
    append_to_document,
    get_general_info,
    search_documents,
    # Embedding tools
    generate_and_store_embedding,
    generate_and_store_document_embedding,
    refresh_entity_embedding,
    refresh_all_embeddings,
    # Intelligence tools
    detect_open_loops,
    find_duplicates,
    flag_for_review,
    clear_review_flag,
    get_items_needing_review,
    delete_entity,
    # Batch operations
    process_extraction,
)

from soml.mcp.resolution import EntityResolver

# For backward compatibility - allow `from soml.mcp import tools as mcp_tools`
from soml.mcp import tools

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
    # Resolution
    "EntityResolver",
    # Module for backward compatibility
    "tools",
]
