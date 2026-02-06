"""
MCP Tools - Tag management tools.

Tools for managing tags across entities and documents:
- get_all_tags: List all tags with usage counts
- add_tags: Add tags to an entity or document
- remove_tags: Remove tags from an entity or document
- find_by_tag: Find all items with a specific tag
- get_related_items: Find items sharing tags with an entity
- create_tag: Create a new tag with metadata
- update_tag: Update tag metadata (color, description)
- delete_tag: Delete a tag
"""

from soml.mcp.tools.base import (
    _get_graph_store,
    _get_registry,
    logger,
)


def get_all_tags() -> list[dict]:
    """
    List all tags with usage counts.
    
    Returns all tags in the system for autocomplete and discovery.
    
    Returns:
        List of tags with:
        - name: Tag name
        - color: Tag color (hex)
        - description: Tag description
        - entity_count: Number of entities with this tag
        - document_count: Number of documents with this tag
        - total_count: Total items with this tag
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    # Get tag metadata from registry
    tags_metadata = registry.get_all_tags()
    tags_by_name = {t["name"]: t for t in tags_metadata}
    
    # Get usage counts from graph
    results = []
    
    try:
        with graph_store.session() as session:
            # Count entities and documents for each tag
            counts = session.run(
                """
                MATCH (t:Tag)
                OPTIONAL MATCH (e:Entity)-[:HAS_TAG]->(t)
                OPTIONAL MATCH (d:Document)-[:HAS_TAG]->(t)
                RETURN t.name as name, 
                       count(DISTINCT e) as entity_count,
                       count(DISTINCT d) as document_count
                """
            )
            
            for record in counts:
                name = record["name"]
                entity_count = record["entity_count"]
                document_count = record["document_count"]
                
                metadata = tags_by_name.get(name, {})
                results.append({
                    "name": name,
                    "color": metadata.get("color"),
                    "description": metadata.get("description"),
                    "entity_count": entity_count,
                    "document_count": document_count,
                    "total_count": entity_count + document_count,
                })
        
        # Add any tags from registry not in graph (unused tags)
        graph_tag_names = {r["name"] for r in results}
        for tag in tags_metadata:
            if tag["name"] not in graph_tag_names:
                results.append({
                    "name": tag["name"],
                    "color": tag.get("color"),
                    "description": tag.get("description"),
                    "entity_count": 0,
                    "document_count": 0,
                    "total_count": 0,
                })
        
    except Exception as e:
        logger.warning(f"Error getting tag counts from graph: {e}")
        # Fall back to just registry metadata
        for tag in tags_metadata:
            results.append({
                "name": tag["name"],
                "color": tag.get("color"),
                "description": tag.get("description"),
                "entity_count": 0,
                "document_count": 0,
                "total_count": 0,
            })
    
    # Sort by usage (most used first)
    results.sort(key=lambda x: x["total_count"], reverse=True)
    
    return results


def add_tags(item_id: str, tags: list[str], item_type: str = "auto") -> dict:
    """
    Add tags to an entity or document.
    
    Args:
        item_id: Entity or document ID
        tags: List of tag names to add
        item_type: "entity", "document", or "auto" (detect automatically)
    
    Returns:
        Result with:
        - success: Whether operation succeeded
        - item_id: ID of the item
        - added_tags: Tags that were added
        - existing_tags: Tags that were already present
        - error: Error message if failed
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    try:
        # Detect item type if auto
        if item_type == "auto":
            item = registry.get(item_id)
            if item:
                if item.get("type") == "document" or item.get("document_type"):
                    item_type = "document"
                else:
                    item_type = "entity"
            else:
                return {
                    "success": False,
                    "item_id": item_id,
                    "error": f"Item {item_id} not found",
                }
        
        # Get current tags
        current_tags = _get_item_tags(item_id, item_type, graph_store)
        current_set = set(current_tags)
        
        # Determine which tags to add
        tags_to_add = [t for t in tags if t not in current_set]
        already_present = [t for t in tags if t in current_set]
        
        # Ensure tag nodes exist and sync
        if tags_to_add:
            for tag in tags_to_add:
                # Ensure tag exists in registry
                registry.upsert_tag(tag)
                # Ensure tag node exists in graph
                graph_store.ensure_tag_node(tag)
            
            # Sync all tags (current + new)
            all_tags = list(current_set | set(tags_to_add))
            graph_store.sync_item_tags(item_id, item_type, all_tags)
        
        logger.info(f"Added tags {tags_to_add} to {item_type} {item_id}")
        
        return {
            "success": True,
            "item_id": item_id,
            "item_type": item_type,
            "added_tags": tags_to_add,
            "existing_tags": already_present,
        }
        
    except Exception as e:
        logger.error(f"Failed to add tags to {item_id}: {e}")
        return {
            "success": False,
            "item_id": item_id,
            "error": str(e),
        }


def remove_tags(item_id: str, tags: list[str], item_type: str = "auto") -> dict:
    """
    Remove tags from an entity or document.
    
    Args:
        item_id: Entity or document ID
        tags: List of tag names to remove
        item_type: "entity", "document", or "auto" (detect automatically)
    
    Returns:
        Result with:
        - success: Whether operation succeeded
        - item_id: ID of the item
        - removed_tags: Tags that were removed
        - not_present: Tags that weren't present
        - error: Error message if failed
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    try:
        # Detect item type if auto
        if item_type == "auto":
            item = registry.get(item_id)
            if item:
                if item.get("type") == "document" or item.get("document_type"):
                    item_type = "document"
                else:
                    item_type = "entity"
            else:
                return {
                    "success": False,
                    "item_id": item_id,
                    "error": f"Item {item_id} not found",
                }
        
        # Get current tags
        current_tags = _get_item_tags(item_id, item_type, graph_store)
        current_set = set(current_tags)
        tags_set = set(tags)
        
        # Determine which tags to remove
        tags_to_remove = list(current_set & tags_set)
        not_present = list(tags_set - current_set)
        
        # Sync remaining tags
        if tags_to_remove:
            remaining_tags = list(current_set - tags_set)
            graph_store.sync_item_tags(item_id, item_type, remaining_tags)
        
        logger.info(f"Removed tags {tags_to_remove} from {item_type} {item_id}")
        
        return {
            "success": True,
            "item_id": item_id,
            "item_type": item_type,
            "removed_tags": tags_to_remove,
            "not_present": not_present,
        }
        
    except Exception as e:
        logger.error(f"Failed to remove tags from {item_id}: {e}")
        return {
            "success": False,
            "item_id": item_id,
            "error": str(e),
        }


def find_by_tag(
    tag_name: str,
    include_entities: bool = True,
    include_documents: bool = True,
) -> list[dict]:
    """
    Find all items with a specific tag.
    
    Args:
        tag_name: Tag to search for
        include_entities: Include entities in results
        include_documents: Include documents in results
    
    Returns:
        List of items with:
        - id: Item ID
        - name: Item name/title
        - type: Item type (entity type or "document")
        - item_type: "entity" or "document"
    """
    graph_store = _get_graph_store()
    
    results = graph_store.find_by_tag(
        tag_name,
        include_entities=include_entities,
        include_documents=include_documents,
    )
    
    return [
        {
            "id": item["id"],
            "name": item.get("name") or item.get("title", "Untitled"),
            "type": item.get("type", "unknown"),
            "item_type": item.get("item_type", "entity"),
        }
        for item in results
    ]


def get_related_items(entity_id: str, include_self: bool = False) -> list[dict]:
    """
    Find items sharing tags with an entity.
    
    Args:
        entity_id: Entity to find related items for
        include_self: Whether to include the entity's own documents
    
    Returns:
        List of related items with:
        - id: Item ID
        - name: Item name/title
        - type: Item type
        - item_type: "entity" or "document"
        - shared_tags: Tags shared with the source entity
    """
    graph_store = _get_graph_store()
    
    results = graph_store.find_related_by_tags(entity_id)
    
    output = []
    for item in results:
        # Skip self's documents if not requested
        if not include_self and item.get("parent_entity_id") == entity_id:
            continue
        
        output.append({
            "id": item["id"],
            "name": item.get("name") or item.get("title", "Untitled"),
            "type": item.get("type", "unknown"),
            "item_type": item.get("item_type", "entity"),
            "shared_tags": item.get("shared_tags", []),
        })
    
    return output


def create_tag(
    name: str,
    color: str | None = None,
    description: str | None = None,
) -> dict:
    """
    Create a new tag with metadata.
    
    Args:
        name: Tag name (required)
        color: Tag color (hex, e.g., "#ff5722")
        description: Tag description
    
    Returns:
        Created tag info with:
        - success: Whether creation succeeded
        - name: Tag name
        - color: Tag color
        - description: Tag description
        - existed: Whether tag already existed
        - error: Error message if failed
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    try:
        # Check if tag exists
        existing = registry.search_tags(name)
        existed = any(t["name"] == name for t in existing)
        
        # Create/update in registry
        registry.upsert_tag(name, color=color, description=description)
        
        # Ensure node exists in graph
        graph_store.ensure_tag_node(name, color=color)
        
        logger.info(f"Created tag '{name}'")
        
        return {
            "success": True,
            "name": name,
            "color": color,
            "description": description,
            "existed": existed,
        }
        
    except Exception as e:
        logger.error(f"Failed to create tag '{name}': {e}")
        return {
            "success": False,
            "name": name,
            "error": str(e),
        }


def update_tag(
    name: str,
    color: str | None = None,
    description: str | None = None,
) -> dict:
    """
    Update tag metadata.
    
    Args:
        name: Tag name to update
        color: New color (hex)
        description: New description
    
    Returns:
        Update result with:
        - success: Whether update succeeded
        - name: Tag name
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Check if tag exists
        existing = registry.search_tags(name)
        if not any(t["name"] == name for t in existing):
            return {
                "success": False,
                "name": name,
                "error": f"Tag '{name}' not found",
            }
        
        # Update in registry
        registry.upsert_tag(name, color=color, description=description)
        
        logger.info(f"Updated tag '{name}'")
        
        return {
            "success": True,
            "name": name,
        }
        
    except Exception as e:
        logger.error(f"Failed to update tag '{name}': {e}")
        return {
            "success": False,
            "name": name,
            "error": str(e),
        }


def delete_tag(name: str, force: bool = False) -> dict:
    """
    Delete a tag.
    
    Args:
        name: Tag name to delete
        force: If True, delete even if tag is in use
    
    Returns:
        Delete result with:
        - success: Whether delete succeeded
        - name: Tag name
        - was_in_use: Whether tag was being used
        - error: Error message if failed
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    try:
        # Check if tag is in use
        items = find_by_tag(name)
        in_use = len(items) > 0
        
        if in_use and not force:
            return {
                "success": False,
                "name": name,
                "was_in_use": True,
                "item_count": len(items),
                "error": f"Tag '{name}' is in use by {len(items)} items. Use force=True to delete anyway.",
            }
        
        # Delete from graph
        with graph_store.session() as session:
            session.run(
                """
                MATCH (t:Tag {name: $name})
                DETACH DELETE t
                """,
                name=name
            )
        
        # Delete from registry
        with registry._get_connection() as conn:
            conn.execute("DELETE FROM tags WHERE name = ?", (name,))
            conn.commit()
        
        logger.info(f"Deleted tag '{name}'")
        
        return {
            "success": True,
            "name": name,
            "was_in_use": in_use,
        }
        
    except Exception as e:
        logger.error(f"Failed to delete tag '{name}': {e}")
        return {
            "success": False,
            "name": name,
            "error": str(e),
        }


# ============================================
# Helper Functions
# ============================================

def _get_item_tags(item_id: str, item_type: str, graph_store) -> list[str]:
    """Get tags for an item from the graph."""
    try:
        label = "Entity" if item_type == "entity" else "Document"
        with graph_store.session() as session:
            result = session.run(
                f"""
                MATCH (n:{label} {{id: $item_id}})-[:HAS_TAG]->(t:Tag)
                RETURN t.name as tag
                """,
                item_id=item_id
            )
            return [record["tag"] for record in result]
    except Exception:
        return []


__all__ = [
    "get_all_tags",
    "add_tags",
    "remove_tags",
    "find_by_tag",
    "get_related_items",
    "create_tag",
    "update_tag",
    "delete_tag",
]

