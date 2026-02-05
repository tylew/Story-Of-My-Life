"""
MCP Tools - Relationship management tools.

Tools for managing relationships between entities:
- link_entities: Create relationships
- unlink_entities: Remove relationships
- get_entity_relationships: Get all relationships for an entity
- add_relationship: Add with audit trail
- replace_relationship: Replace one type with another
- propose_relationship_changes: Generate proposals for LLM
- apply_relationship_proposal: Apply approved proposals
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from soml.core.types import RelationshipCategory
from soml.mcp.tools.base import (
    LinkResult,
    _get_graph_store,
    _get_registry,
    logger,
)


def link_entities(
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: dict | None = None,
) -> LinkResult:
    """
    Create or update a relationship between two entities.
    
    Idempotent - calling twice with same args won't duplicate.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (e.g., "family", "works_at", "invested_in")
        properties: Additional properties (strength, sentiment, notes)
    
    Returns:
        LinkResult with action taken
    """
    graph_store = _get_graph_store()
    properties = properties or {}
    
    # Determine category from type
    personal_types = ["family", "friend", "partner", "coworker", "mentor", "mentee", "acquaintance", "professional"]
    category = RelationshipCategory.PERSONAL if rel_type in personal_types else RelationshipCategory.STRUCTURAL
    
    try:
        # Check if relationship already exists
        existing = graph_store.get_relationships(source_id)
        for rel in existing:
            if rel.get("other_id") == target_id and rel.get("type") == rel_type:
                # Already exists
                return LinkResult(
                    action="exists",
                    relationship_id=rel.get("id"),
                )
        
        # Create new
        graph_store.create_relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=rel_type,
            category=category,
            properties=properties,
        )
        
        logger.info(f"Created relationship: {source_id} -[{rel_type}]-> {target_id}")
        
        return LinkResult(
            action="created",
            relationship_id=f"{source_id}_{rel_type}_{target_id}",
        )
        
    except Exception as e:
        logger.error(f"Failed to create relationship: {e}")
        return LinkResult(
            action="failed",
            error=str(e),
        )


def unlink_entities(
    source_id: str,
    target_id: str,
    rel_type: str,
) -> bool:
    """
    Remove a relationship between two entities.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type to remove
    
    Returns:
        True if relationship was removed
    """
    graph_store = _get_graph_store()
    
    try:
        with graph_store.session() as session:
            result = session.run(
                """
                MATCH (a:Entity {id: $source_id})-[r:RELATES_TO {type: $rel_type}]->(b:Entity {id: $target_id})
                DELETE r
                RETURN count(r) as deleted
                """,
                source_id=source_id,
                target_id=target_id,
                rel_type=rel_type,
            )
            record = result.single()
            return record["deleted"] > 0 if record else False
            
    except Exception as e:
        logger.error(f"Failed to unlink entities: {e}")
        return False


def get_entity_relationships(
    entity_id: str,
    direction: str = "both",
    include_entity_details: bool = True,
) -> list[dict]:
    """
    Get all relationships for an entity.
    
    This is the primary tool for LLMs to review existing relationships
    before proposing changes.
    
    Args:
        entity_id: Entity ID to get relationships for
        direction: "outgoing", "incoming", or "both"
        include_entity_details: Include name/type of related entities
    
    Returns:
        List of relationship dicts with full context
    """
    graph_store = _get_graph_store()
    registry = _get_registry()
    
    try:
        rels = graph_store.get_relationships(entity_id, direction)
        
        results = []
        for rel in rels:
            rel_dict = {
                "id": rel.get("id"),
                "type": rel.get("type"),
                "category": rel.get("category"),
                "direction": "outgoing" if rel.get("source_id") == entity_id else "incoming",
                "other_entity_id": rel.get("other_id"),
                "properties": rel.get("properties", {}),
                "created_at": rel.get("created_at"),
            }
            
            if include_entity_details:
                other = registry.get(rel.get("other_id"))
                if other:
                    rel_dict["other_entity_name"] = other.get("name")
                    rel_dict["other_entity_type"] = other.get("type")
            
            results.append(rel_dict)
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get relationships: {e}")
        return []


def add_relationship(
    source_id: str,
    target_id: str,
    rel_type: str,
    reason: str | None = None,
    properties: dict | None = None,
) -> LinkResult:
    """
    Add a new relationship between entities.
    
    Use this when creating a completely new relationship.
    For updating existing relationships, use replace_relationship.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type
        reason: Why this relationship is being created (for audit)
        properties: Additional properties
    
    Returns:
        LinkResult with action taken
    """
    props = properties or {}
    if reason:
        props["creation_reason"] = reason
        props["created_at"] = datetime.now().isoformat()
    
    return link_entities(source_id, target_id, rel_type, props)


def replace_relationship(
    source_id: str,
    target_id: str,
    old_type: str,
    new_type: str,
    reason: str | None = None,
    properties: dict | None = None,
) -> LinkResult:
    """
    Replace an existing relationship type with a new one.
    
    Use this for transitions like:
    - works_with → worked_with (when someone leaves)
    - friend → partner (relationship upgraded)
    - acquaintance → friend (relationship strengthened)
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        old_type: Current relationship type to replace
        new_type: New relationship type
        reason: Why this change is happening (for audit)
        properties: Additional/updated properties
    
    Returns:
        LinkResult with action taken
    """
    props = properties or {}
    
    try:
        # Remove old relationship
        removed = unlink_entities(source_id, target_id, old_type)
        
        if not removed:
            # Try the reverse direction
            removed = unlink_entities(target_id, source_id, old_type)
        
        if not removed:
            return LinkResult(
                action="failed",
                error=f"No existing '{old_type}' relationship found to replace",
            )
        
        # Add audit info
        props["replaced_from"] = old_type
        props["replacement_reason"] = reason
        props["replaced_at"] = datetime.now().isoformat()
        
        # Create new relationship
        return link_entities(source_id, target_id, new_type, props)
        
    except Exception as e:
        logger.error(f"Failed to replace relationship: {e}")
        return LinkResult(
            action="failed",
            error=str(e),
        )


@dataclass
class RelationshipProposal:
    """A proposed relationship change for user review."""
    
    action: Literal["add", "replace", "remove"]
    """Type of change: add new, replace existing, or remove."""
    
    source_id: str
    """Source entity ID."""
    
    target_id: str
    """Target entity ID."""
    
    source_name: str
    """Source entity name (for display)."""
    
    target_name: str
    """Target entity name (for display)."""
    
    new_type: str | None
    """New relationship type (for add/replace)."""
    
    old_type: str | None = None
    """Existing relationship type (for replace/remove)."""
    
    reason: str | None = None
    """LLM's reasoning for this proposal."""


def propose_relationship_changes(
    entity_ids: list[str],
    context: str,
    existing_relationships: list[dict] | None = None,
) -> dict:
    """
    Analyze entities and propose relationship changes.
    
    This is called by the LLM agent to generate proposals.
    The LLM reviews existing relationships and proposes:
    - New relationships to ADD
    - Existing relationships to REPLACE (type change)
    - Relationships to REMOVE (if context suggests they're no longer valid)
    
    Args:
        entity_ids: IDs of entities to analyze
        context: The user input/context for the change
        existing_relationships: Pre-fetched relationships (optional, will fetch if not provided)
    
    Returns:
        Dict with entity info and existing relationships for LLM to analyze
    """
    registry = _get_registry()
    
    # Gather existing relationships for all entities
    all_existing = existing_relationships or []
    if not existing_relationships:
        for entity_id in entity_ids:
            rels = get_entity_relationships(entity_id, include_entity_details=True)
            all_existing.extend(rels)
    
    # Build entity name map
    entity_names = {}
    for entity_id in entity_ids:
        entity = registry.get(entity_id)
        if entity:
            entity_names[entity_id] = entity.get("name", "Unknown")
    
    # Return existing relationships summary for LLM to analyze
    # The actual proposal generation is done by the LLM, not this function
    return {
        "entity_ids": entity_ids,
        "entity_names": entity_names,
        "existing_relationships": [
            {
                "source_id": r.get("source_id") or (r.get("other_entity_id") if r.get("direction") == "incoming" else entity_ids[0]),
                "target_id": r.get("target_id") or (entity_ids[0] if r.get("direction") == "incoming" else r.get("other_entity_id")),
                "source_name": r.get("source_name") or entity_names.get(r.get("source_id", ""), "Unknown"),
                "target_name": r.get("other_entity_name", "Unknown"),
                "type": r.get("type"),
                "category": r.get("category"),
            }
            for r in all_existing
        ],
        "context": context,
    }


def apply_relationship_proposal(
    proposal: dict,
) -> LinkResult:
    """
    Apply a user-approved relationship proposal.
    
    This is called after the user approves a proposal.
    
    Args:
        proposal: The approved proposal dict with keys:
            - action: "add", "replace", or "remove"
            - source_id, target_id
            - new_type (for add/replace)
            - old_type (for replace/remove)
            - reason (optional)
    
    Returns:
        LinkResult with action taken
    """
    action = proposal.get("action")
    source_id = proposal.get("source_id")
    target_id = proposal.get("target_id")
    new_type = proposal.get("new_type")
    old_type = proposal.get("old_type")
    reason = proposal.get("reason")
    
    if action == "add":
        return add_relationship(source_id, target_id, new_type, reason)
    
    elif action == "replace":
        return replace_relationship(source_id, target_id, old_type, new_type, reason)
    
    elif action == "remove":
        success = unlink_entities(source_id, target_id, old_type)
        return LinkResult(
            action="updated" if success else "failed",
            error=None if success else "Failed to remove relationship",
        )
    
    else:
        return LinkResult(
            action="failed",
            error=f"Unknown action: {action}",
        )


__all__ = [
    "link_entities",
    "unlink_entities",
    "get_entity_relationships",
    "add_relationship",
    "replace_relationship",
    "RelationshipProposal",
    "propose_relationship_changes",
    "apply_relationship_proposal",
]

