"""
MCP Tools - Query and search tools.

Tools for retrieving and searching data:
- get_entity: Get entity by ID
- search_entities: Full-text search
- get_relationships: Get relationships for an entity
- get_timeline: Get timeline of events
- semantic_search: Vector similarity search
- find_entities_by_name: Find entities with disambiguation support
- get_entity_with_documents: Get entity with all documents
"""

from datetime import date, datetime, timedelta

from soml.core.types import EntityType
from soml.mcp.tools.base import (
    _get_graph_store,
    _get_md_store,
    _get_registry,
    logger,
)


def get_entity(entity_id: str) -> dict | None:
    """
    Get an entity by ID.
    
    Returns:
        Entity dict with metadata and content, or None
    """
    registry = _get_registry()
    md_store = _get_md_store()
    
    doc = registry.get(entity_id)
    if not doc:
        return None
    
    # Get full content
    md_doc = md_store.read_by_id(entity_id)
    content = md_doc.get("content", "") if md_doc else ""
    
    return {
        **doc,
        "content": content,
    }


def search_entities(
    query: str,
    entity_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search for entities by name or content.
    
    Args:
        query: Search query
        entity_type: Optional type filter
        limit: Maximum results
    
    Returns:
        List of matching entity dicts
    """
    registry = _get_registry()
    
    results = registry.search(query, entity_type, limit)
    return results


def get_relationships(
    entity_id: str,
    direction: str = "both",
    rel_type: str | None = None,
) -> list[dict]:
    """
    Get relationships for an entity.
    
    Args:
        entity_id: Entity ID
        direction: "outgoing", "incoming", or "both"
        rel_type: Optional relationship type filter
    
    Returns:
        List of relationship dicts
    """
    graph_store = _get_graph_store()
    
    relationships = graph_store.get_relationships(entity_id, direction)
    
    if rel_type:
        relationships = [r for r in relationships if r.get("type") == rel_type]
    
    return relationships


def get_timeline(
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    types: list[str] | None = None,
) -> list[dict]:
    """
    Get timeline of events.
    
    Args:
        start_date: Start of timeline (default: 7 days ago)
        end_date: End of timeline (default: today)
        types: Optional list of entity types to include
    
    Returns:
        List of timeline entries sorted by date
    """
    registry = _get_registry()
    
    # Parse dates
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)
    
    if not start_date:
        start_date = date.today() - timedelta(days=7)
    if not end_date:
        end_date = date.today()
    
    types = types or ["event", "note"]
    
    timeline = []
    for entity_type in types:
        entities = registry.list_by_type(entity_type)
        for entity in entities:
            created = entity.get("created_at")
            if created:
                try:
                    dt = datetime.fromisoformat(created).date()
                    if start_date <= dt <= end_date:
                        timeline.append({
                            "id": entity.get("id"),
                            "date": created,
                            "name": entity.get("name") or entity.get("title", "Unknown"),
                            "type": entity.get("type"),
                        })
                except (ValueError, TypeError):
                    pass
    
    # Sort by date descending
    timeline.sort(key=lambda x: x["date"], reverse=True)
    return timeline


def semantic_search(
    query: str,
    limit: int = 10,
    entity_type: str | None = None,
) -> list[dict]:
    """
    Semantic search using vector embeddings.
    
    This generates an embedding for the query and finds similar entities
    based on cosine similarity of their embeddings.
    
    Args:
        query: Natural language query
        limit: Maximum results
        entity_type: Optional type filter
    
    Returns:
        List of matching entities with similarity scores
    """
    from soml.mcp.tools.embedding import _generate_embedding_sync
    
    graph_store = _get_graph_store()
    
    try:
        # Generate embedding for the query using sync client
        query_embedding = _generate_embedding_sync(query)
        
        if not query_embedding:
            logger.warning("Failed to generate query embedding, falling back to fulltext")
            return graph_store.fulltext_search(query, limit)
        
        # Search using vector similarity
        results = graph_store.vector_search(
            embedding=query_embedding,
            limit=limit,
            entity_type=entity_type,
        )
        
        # Normalize keys: Neo4j uses entity_type, we use type for consistency
        for r in results:
            entity = r.get("entity", {})
            if "entity_type" in entity and "type" not in entity:
                entity["type"] = entity["entity_type"]
        
        return results
        
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to fulltext: {e}")
        # Fall back to full-text search
        return graph_store.fulltext_search(query, limit)


def find_entities_by_name(
    name: str,
    entity_type: str | None = None,
    exact: bool = False,
) -> list[dict]:
    """
    Find entities by name with disambiguation support.
    
    Use this when you need to resolve a name mention to specific entities.
    Returns multiple candidates if the name is ambiguous.
    
    Args:
        name: Name to search for (e.g., "Frank", "Project Alpha")
        entity_type: Optional type filter (person, project, goal, event, period)
        exact: If True, only return exact matches; if False, include similar names
    
    Returns:
        List of matching entities with:
        - id: Entity ID
        - name: Entity name
        - type: Entity type
        - disambiguator: Contextual description (for people)
        - match_score: Match confidence (1.0 for exact, lower for fuzzy)
        - document_count: Number of documents for this entity
    """
    registry = _get_registry()
    md_store = _get_md_store()
    
    # Search for entities
    results = registry.search(name, entity_type=entity_type, limit=20)
    
    # Filter and score results
    candidates = []
    name_lower = name.lower().strip()
    
    for result in results:
        result_name = (result.get("name") or "").lower().strip()
        
        # Calculate match confidence
        if result_name == name_lower:
            confidence = 1.0
        elif name_lower in result_name or result_name in name_lower:
            confidence = 0.8
        else:
            # Fuzzy match - check word overlap
            name_words = set(name_lower.split())
            result_words = set(result_name.split())
            overlap = len(name_words & result_words)
            confidence = overlap / max(len(name_words), 1) * 0.6
        
        if exact and confidence < 1.0:
            continue
        
        if confidence < 0.3:
            continue
        
        # Get document count for this entity
        docs = registry.list_entity_documents(result["id"])
        
        # Get disambiguator from markdown if available
        md_doc = md_store.read_by_id(result["id"], result.get("type"))
        disambiguator = None
        if md_doc:
            disambiguator = md_doc.get("metadata", {}).get("disambiguator")
        
        candidates.append({
            "id": result["id"],
            "name": result.get("name"),
            "type": result.get("type"),
            "disambiguator": disambiguator,
            "match_score": confidence,
            "document_count": len(docs) if docs else 0,
        })
    
    # Sort by confidence
    candidates.sort(key=lambda x: x["match_score"], reverse=True)
    
    return candidates


def get_entity_with_documents(entity_id: str) -> dict | None:
    """
    Get an entity with all its documents and relationships.
    
    Use this to get comprehensive information about an entity including
    their General Info document content.
    
    Args:
        entity_id: Entity ID
    
    Returns:
        Entity dict with:
        - entity: Full entity data
        - general_info: General Info document content
        - documents: List of other documents
        - relationships: List of relationships
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # Get entity from registry
    entity = registry.get(str(entity_id))
    if not entity:
        return None
    
    # Get full entity data from markdown
    md_doc = md_store.read_by_id(entity_id, entity.get("type"))
    entity_data = md_doc.get("metadata", {}) if md_doc else entity
    
    # Get General Info document
    general_info = md_store.get_general_info_document(entity_id)
    general_info_content = None
    if general_info:
        general_info_content = general_info.get("content", "")
    
    # Get other documents
    all_docs = registry.list_entity_documents(str(entity_id))
    documents = []
    for doc in all_docs:
        if doc.get("document_type") != "general_info":
            full_doc = md_store.read_document(doc["id"])
            documents.append({
                "id": doc["id"],
                "name": doc.get("name"),
                "type": doc.get("document_type"),
                "content": full_doc.get("content") if full_doc else None,
            })
    
    # Get relationships
    relationships = graph_store.get_relationships(str(entity_id))
    
    return {
        "entity": entity_data,
        "general_info": general_info_content,
        "documents": documents,
        "relationships": relationships,
    }


__all__ = [
    "get_entity",
    "search_entities",
    "get_relationships",
    "get_timeline",
    "semantic_search",
    "find_entities_by_name",
    "get_entity_with_documents",
]

