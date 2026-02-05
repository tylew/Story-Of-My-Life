"""
MCP Tools - Intelligence and review tools.

Tools for analysis and open loop detection:
- detect_open_loops: Find stale relationships, projects, items needing review
- find_duplicates: Find potential duplicate entities
- flag_for_review: Mark an entity for user review
- clear_review_flag: Remove review flag from entity
- get_items_needing_review: Get all flagged items
"""

from datetime import datetime

from soml.core.types import EntityType
from soml.mcp.tools.base import (
    _get_graph_store,
    _get_md_store,
    _get_registry,
    _get_resolver,
    logger,
)


def detect_open_loops() -> list[dict]:
    """
    Detect open loops in the knowledge graph.
    
    Includes:
    - Stale relationships (no interaction in 30 days)
    - Stale projects (no activity in 14 days)
    - Items flagged for review (by agent)
    
    Returns:
        List of open loop dicts with type, entity, and urgency
    """
    graph_store = _get_graph_store()
    
    loops = []
    
    # Items needing review (highest priority)
    review_items = get_items_needing_review()
    for item in review_items:
        loops.append({
            "type": "needs_review",
            "entity_id": item["id"],
            "entity_name": item["name"],
            "entity_type": item["type"],
            "urgency": 90,  # High priority
            "prompt": f"Review needed for {item['type']} '{item['name']}': {item.get('review_reason', 'No reason provided')}",
            "review_reason": item.get("review_reason"),
        })
    
    # Stale relationships (no interaction in 30 days)
    stale_rels = graph_store.get_stale_relationships(30)
    for rel in stale_rels:
        loops.append({
            "type": "relationship",
            "entity_id": rel["person"]["id"],
            "entity_name": rel["person"]["name"],
            "urgency": 50,
            "prompt": f"You haven't interacted with {rel['other']['name']} recently. Want to check in?",
        })
    
    # Stale projects (no activity in 14 days)
    stale_projects = graph_store.get_stale_projects(14)
    for project in stale_projects:
        loops.append({
            "type": "project",
            "entity_id": project["id"],
            "entity_name": project["name"],
            "urgency": 70,
            "prompt": f"Project '{project['name']}' hasn't had activity recently. Any updates?",
        })
    
    # Sort by urgency (highest first)
    loops.sort(key=lambda x: x["urgency"], reverse=True)
    
    return loops


def find_duplicates() -> list[dict]:
    """
    Find potential duplicate entities.
    
    Returns:
        List of duplicate sets with entity pairs
    """
    registry = _get_registry()
    resolver = _get_resolver()
    
    duplicates = []
    
    for entity_type in [EntityType.PERSON, EntityType.PROJECT]:
        entities = registry.list_by_type(entity_type)
        
        # Compare each pair
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                # Check for name similarity
                name1 = (e1.get("name") or "").lower()
                name2 = (e2.get("name") or "").lower()
                
                if name1 and name2:
                    # Exact match
                    if name1 == name2:
                        duplicates.append({
                            "entities": [e1, e2],
                            "reason": "Exact name match",
                            "confidence": 1.0,
                        })
                    # One contains the other
                    elif name1 in name2 or name2 in name1:
                        duplicates.append({
                            "entities": [e1, e2],
                            "reason": "Name overlap",
                            "confidence": 0.7,
                        })
    
    return duplicates


def flag_for_review(
    entity_id: str,
    reason: str,
) -> dict:
    """
    Flag an entity or document for user review.
    
    This creates an open loop that will be surfaced to the user.
    Use when:
    - Information seems incomplete or uncertain
    - Multiple interpretations are possible
    - Data quality is questionable
    - User confirmation would be valuable
    
    Args:
        entity_id: ID of the entity to flag
        reason: Why this needs review
    
    Returns:
        Result with success status
    """
    md_store = _get_md_store()
    registry = _get_registry()
    
    # Get entity from registry
    entity_data = registry.get(str(entity_id))
    if not entity_data:
        return {"success": False, "error": "Entity not found"}
    
    entity_type = entity_data.get("type")
    
    # Read the markdown file
    md_doc = md_store.read_by_id(entity_id, entity_type)
    if not md_doc:
        return {"success": False, "error": "Could not read entity file"}
    
    # Update the metadata
    metadata = md_doc.get("metadata", {})
    metadata["needs_review"] = True
    metadata["review_reason"] = reason
    metadata["updated_at"] = datetime.now().isoformat()
    
    # Write back
    md_store.update_frontmatter(entity_id, entity_type, metadata)
    
    logger.info(f"Flagged entity {entity_id} for review: {reason}")
    
    return {
        "success": True,
        "entity_id": entity_id,
        "reason": reason,
    }


def clear_review_flag(entity_id: str) -> dict:
    """
    Clear the review flag from an entity.
    
    Call this after a user has reviewed and confirmed an entity.
    
    Args:
        entity_id: ID of the entity
    
    Returns:
        Result with success status
    """
    md_store = _get_md_store()
    registry = _get_registry()
    
    entity_data = registry.get(str(entity_id))
    if not entity_data:
        return {"success": False, "error": "Entity not found"}
    
    entity_type = entity_data.get("type")
    
    md_doc = md_store.read_by_id(entity_id, entity_type)
    if not md_doc:
        return {"success": False, "error": "Could not read entity file"}
    
    metadata = md_doc.get("metadata", {})
    metadata["needs_review"] = False
    metadata["review_reason"] = None
    metadata["updated_at"] = datetime.now().isoformat()
    
    md_store.update_frontmatter(entity_id, entity_type, metadata)
    
    logger.info(f"Cleared review flag from entity {entity_id}")
    
    return {"success": True, "entity_id": entity_id}


def get_items_needing_review() -> list[dict]:
    """
    Get all entities and documents flagged for review.
    
    These are surfaced as open loops in the UI.
    
    Returns:
        List of items with id, name, type, and review_reason
    """
    md_store = _get_md_store()
    registry = _get_registry()
    
    items = []
    
    # Check all entity types
    for entity_type in [EntityType.PERSON, EntityType.PROJECT, EntityType.GOAL, 
                        EntityType.EVENT, EntityType.PERIOD, EntityType.DOCUMENT]:
        entities = registry.list_by_type(entity_type)
        
        for entity in entities:
            md_doc = md_store.read_by_id(entity["id"], entity_type)
            if md_doc:
                metadata = md_doc.get("metadata", {})
                if metadata.get("needs_review"):
                    items.append({
                        "id": entity["id"],
                        "name": entity.get("name") or entity.get("title"),
                        "type": entity_type if isinstance(entity_type, str) else entity_type.value,
                        "review_reason": metadata.get("review_reason"),
                        "created_at": metadata.get("created_at"),
                    })
    
    return items


def delete_entity(entity_id: str) -> dict:
    """
    Delete an entity and its associated documents.
    
    Args:
        entity_id: ID of the entity to delete
    
    Returns:
        Result with success status
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # Get entity from registry
    entity = registry.get(str(entity_id))
    if not entity:
        return {"success": False, "error": "Entity not found"}
    
    entity_type = entity.get("type")
    
    try:
        # Delete from graph
        graph_store.delete_node(entity_id)
        
        # Delete documents
        docs = registry.list_entity_documents(entity_id)
        for doc in docs:
            md_store.delete(doc["id"], "document")
            registry.delete(doc["id"])
        
        # Delete entity markdown
        md_store.delete(entity_id, entity_type)
        
        # Delete from registry
        registry.delete(entity_id)
        
        logger.info(f"Deleted entity {entity_id} ({entity_type})")
        
        return {"success": True, "entity_id": entity_id}
        
    except Exception as e:
        logger.error(f"Failed to delete entity {entity_id}: {e}")
        return {"success": False, "error": str(e)}


__all__ = [
    "detect_open_loops",
    "find_duplicates",
    "flag_for_review",
    "clear_review_flag",
    "get_items_needing_review",
    "delete_entity",
]

