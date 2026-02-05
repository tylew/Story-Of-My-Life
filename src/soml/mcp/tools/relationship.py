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

Standard Relationship Types:
- Personal: friend, family, partner, works_with, worked_with, mentor, mentee, acquaintance
- Professional: collaborator, investor, advisor, client, vendor, competitor
- Structural: part_of, depends_on, blocks, references, stakeholder_of, during
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

from soml.core.types import RelationshipCategory
from soml.mcp.tools.base import (
    LinkResult,
    _get_graph_store,
    _get_registry,
    logger,
)


# ============================================
# Standard Relationship Types
# ============================================

# Personal relationships (between people)
PERSONAL_RELATIONSHIP_TYPES = {
    "friend": "A friendship relationship",
    "family": "Family member (parent, sibling, child, etc.)",
    "partner": "Romantic partner or spouse",
    "works_with": "Currently working together",
    "worked_with": "Previously worked together",
    "coworker": "Colleague at same organization",
    "mentor": "Mentor relationship (source mentors target)",
    "mentee": "Mentee relationship (source is mentored by target)",
    "acquaintance": "Casual acquaintance",
    "professional": "Professional contact",
    "collaborator": "Working together on a project",
    "introduced_by": "Was introduced through this person",
}

# Professional/business relationships
PROFESSIONAL_RELATIONSHIP_TYPES = {
    "investor": "Investor relationship",
    "advisor": "Advisory relationship",
    "client": "Client relationship",
    "vendor": "Vendor/supplier relationship",
    "competitor": "Competitive relationship",
    "negotiating_with": "Currently in negotiations",
    "contracted_with": "Under contract",
}

# Structural relationships (between any entities)
STRUCTURAL_RELATIONSHIP_TYPES = {
    "part_of": "Hierarchical containment",
    "depends_on": "Dependency relationship",
    "blocks": "Blocking relationship",
    "references": "Reference/citation",
    "stakeholder_of": "Stakeholder in project/goal",
    "related_to": "General relation",
    "during": "Occurred during a time period",
    "leads_to": "Causal or sequential relationship",
    "derived_from": "Derived or evolved from",
}

# All relationship types
ALL_RELATIONSHIP_TYPES = {
    **PERSONAL_RELATIONSHIP_TYPES,
    **PROFESSIONAL_RELATIONSHIP_TYPES,
    **STRUCTURAL_RELATIONSHIP_TYPES,
}


@dataclass
class RelationshipData:
    """Rich data for a relationship between entities."""
    
    rel_type: str
    """The relationship type (e.g., 'friend', 'works_with')."""
    
    # Core properties
    strength: float = 0.5
    """Relationship strength (0.0-1.0). Higher = stronger connection."""
    
    sentiment: float = 0.0
    """Emotional sentiment (-1.0 to 1.0). Negative = adversarial, positive = positive."""
    
    confidence: float = 0.8
    """How confident we are in this relationship (0.0-1.0)."""
    
    # Context
    context: str | None = None
    """Why/how this relationship exists (e.g., 'met at conference', 'childhood friends')."""
    
    notes: str | None = None
    """Additional notes about the relationship."""
    
    # Temporal
    started_at: str | None = None
    """When the relationship started (ISO date string)."""
    
    ended_at: str | None = None
    """When the relationship ended, if applicable (ISO date string)."""
    
    last_interaction: str | None = None
    """Last known interaction (ISO datetime string)."""
    
    # Source tracking
    source: str = "agent"
    """How this was created: 'user', 'agent', 'import'."""
    
    source_text: str | None = None
    """The original text that led to this relationship."""
    
    # Custom data
    custom_fields: dict = field(default_factory=dict)
    """Any additional custom properties."""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "type": self.rel_type,
            "strength": self.strength,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "context": self.context,
            "notes": self.notes,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "last_interaction": self.last_interaction,
            "source": self.source,
            "source_text": self.source_text,
            **self.custom_fields,
        }


def _get_relationship_category(rel_type: str) -> RelationshipCategory:
    """Determine the category for a relationship type."""
    if rel_type in PERSONAL_RELATIONSHIP_TYPES or rel_type in PROFESSIONAL_RELATIONSHIP_TYPES:
        return RelationshipCategory.PERSONAL
    return RelationshipCategory.STRUCTURAL


def link_entities(
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: dict | None = None,
) -> LinkResult:
    """
    Create a relationship between two entities.
    
    Always creates a new relationship - multiple relationships of the same type
    between the same entities are allowed (e.g., collaborated on multiple projects,
    different contexts for the same connection).
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (see ALL_RELATIONSHIP_TYPES for standard types)
        properties: Rich relationship data including:
            - strength: 0.0-1.0 (default 0.5)
            - sentiment: -1.0 to 1.0 (default 0.0)
            - confidence: 0.0-1.0 (default 0.8)
            - context: Why/how this relationship exists
            - notes: Additional notes
            - started_at: When relationship started
            - ended_at: When relationship ended (if applicable)
            - source_text: Original text that created this
    
    Returns:
        LinkResult with action taken and relationship ID
    """
    graph_store = _get_graph_store()
    properties = properties or {}
    
    # Add relationship ID for uniqueness
    rel_id = str(uuid4())
    properties["id"] = rel_id
    
    # Ensure standard fields have defaults
    properties.setdefault("strength", 0.5)
    properties.setdefault("sentiment", 0.0)
    properties.setdefault("confidence", 0.8)
    properties.setdefault("source", "agent")
    
    # Determine category from type
    category = _get_relationship_category(rel_type)
    
    try:
        # Always create new relationship (no duplicate check)
        graph_store.create_relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=rel_type,
            category=category,
            properties=properties,
        )
        
        logger.info(f"Created relationship: {source_id} -[{rel_type}]-> {target_id} (id: {rel_id})")
        
        return LinkResult(
            action="created",
            relationship_id=rel_id,
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
    relationship_id: str | None = None,
) -> bool:
    """
    Remove a relationship between two entities.
    
    Can remove by relationship ID (specific) or by type (all matching).
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type to remove
        relationship_id: If provided, only removes the specific relationship with this ID
    
    Returns:
        True if at least one relationship was removed
    """
    graph_store = _get_graph_store()
    
    try:
        with graph_store.session() as session:
            if relationship_id:
                # Remove specific relationship by ID
                result = session.run(
                    """
                    MATCH (a:Entity {id: $source_id})-[r:RELATES_TO {id: $rel_id}]->(b:Entity {id: $target_id})
                    DELETE r
                    RETURN count(r) as deleted
                    """,
                    source_id=source_id,
                    target_id=target_id,
                    rel_id=relationship_id,
                )
            else:
                # Remove all relationships of this type between the entities
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


def unlink_relationship_by_id(relationship_id: str) -> bool:
    """
    Remove a specific relationship by its unique ID.
    
    Args:
        relationship_id: The unique relationship ID
    
    Returns:
        True if relationship was removed
    """
    graph_store = _get_graph_store()
    
    try:
        with graph_store.session() as session:
            result = session.run(
                """
                MATCH ()-[r:RELATES_TO {id: $rel_id}]->()
                DELETE r
                RETURN count(r) as deleted
                """,
                rel_id=relationship_id,
            )
            record = result.single()
            deleted = record["deleted"] > 0 if record else False
            if deleted:
                logger.info(f"Removed relationship: {relationship_id}")
            return deleted
            
    except Exception as e:
        logger.error(f"Failed to remove relationship by ID: {e}")
        return False


def get_entity_relationships(
    entity_id: str,
    direction: str = "both",
    include_entity_details: bool = True,
    rel_type: str | None = None,
) -> list[dict]:
    """
    Get all relationships for an entity with full rich data.
    
    This is the primary tool for LLMs to review existing relationships
    before proposing changes.
    
    Args:
        entity_id: Entity ID to get relationships for
        direction: "outgoing", "incoming", or "both"
        include_entity_details: Include name/type of related entities
        rel_type: Filter by specific relationship type (optional)
    
    Returns:
        List of relationship dicts with full rich data including:
        - id: Unique relationship ID
        - type: Relationship type
        - category: personal or structural
        - direction: outgoing or incoming
        - other_entity_id: ID of the other entity
        - other_entity_name/type: Details of other entity (if include_entity_details)
        - strength: Relationship strength 0.0-1.0
        - sentiment: Emotional sentiment -1.0 to 1.0
        - confidence: Confidence level 0.0-1.0
        - context: Why/how the relationship exists
        - notes: Additional notes
        - started_at/ended_at: Temporal bounds
        - created_at/updated_at: Timestamps
    """
    graph_store = _get_graph_store()
    registry = _get_registry()
    
    try:
        rels = graph_store.get_relationships(entity_id, direction)
        
        results = []
        for rel in rels:
            # Filter by type if specified
            if rel_type and rel.get("type") != rel_type:
                continue
            
            rel_dict = {
                # Core identifiers
                "id": rel.get("id"),
                "type": rel.get("type"),
                "category": rel.get("category"),
                "direction": "outgoing" if rel.get("source_id") == entity_id else "incoming",
                "other_entity_id": rel.get("other_id"),
                
                # Rich data fields
                "strength": rel.get("strength", 0.5),
                "sentiment": rel.get("sentiment", 0.0),
                "confidence": rel.get("confidence", 0.8),
                "context": rel.get("context"),
                "notes": rel.get("notes"),
                
                # Temporal
                "started_at": rel.get("started_at"),
                "ended_at": rel.get("ended_at"),
                "last_interaction": rel.get("last_interaction"),
                "created_at": rel.get("created_at"),
                "updated_at": rel.get("updated_at"),
                
                # Source tracking
                "source": rel.get("source", "agent"),
                "source_text": rel.get("source_text"),
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
    context: str | None = None,
    strength: float | None = None,
    sentiment: float | None = None,
    confidence: float | None = None,
    started_at: str | None = None,
    properties: dict | None = None,
) -> LinkResult:
    """
    Add a new relationship between entities with rich data.
    
    Always creates a new relationship - multiple relationships of the same type
    between entities are allowed.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (see ALL_RELATIONSHIP_TYPES for standards)
        reason: Why this relationship is being created (for audit)
        context: Context for this relationship (e.g., "met at conference")
        strength: Relationship strength 0.0-1.0 (default 0.5)
        sentiment: Emotional sentiment -1.0 to 1.0 (default 0.0)
        confidence: Confidence in this relationship 0.0-1.0 (default 0.8)
        started_at: When the relationship started (ISO date string)
        properties: Additional custom properties
    
    Returns:
        LinkResult with action taken and relationship ID
    """
    props = properties or {}
    
    # Add rich data
    if reason:
        props["notes"] = reason
    if context:
        props["context"] = context
    if strength is not None:
        props["strength"] = max(0.0, min(1.0, strength))
    if sentiment is not None:
        props["sentiment"] = max(-1.0, min(1.0, sentiment))
    if confidence is not None:
        props["confidence"] = max(0.0, min(1.0, confidence))
    if started_at:
        props["started_at"] = started_at
    
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
    # Relationship type constants
    "PERSONAL_RELATIONSHIP_TYPES",
    "PROFESSIONAL_RELATIONSHIP_TYPES",
    "STRUCTURAL_RELATIONSHIP_TYPES",
    "ALL_RELATIONSHIP_TYPES",
    # Rich data class
    "RelationshipData",
    # Core functions
    "link_entities",
    "unlink_entities",
    "unlink_relationship_by_id",
    "get_entity_relationships",
    "add_relationship",
    "replace_relationship",
    # Proposal types and functions
    "RelationshipProposal",
    "propose_relationship_changes",
    "apply_relationship_proposal",
]

