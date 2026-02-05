"""
MCP Tools - Document management tools.

Tools for managing documents:
- append_to_document: Append content to General Info
- get_general_info: Get General Info document for an entity
- search_documents: Full-text search across documents
"""

from soml.core.types import Source
from soml.mcp.tools.base import (
    _get_md_store,
    _get_registry,
    logger,
)


def append_to_document(
    entity_id: str,
    content: str,
    source: str = "agent",
) -> bool:
    """
    Append content to an entity's General Info document.
    
    Args:
        entity_id: Entity ID
        content: Content to append
        source: Source ("user" or "agent")
    
    Returns:
        True if successful
    """
    md_store = _get_md_store()
    
    # Find or create General Info document
    general_info = md_store.get_general_info_document(entity_id)
    
    if general_info:
        return md_store.append_to_document(
            doc_id=general_info["metadata"].get("id"),
            content=content,
            source=Source(source),
        )
    
    # TODO: Create General Info document if it doesn't exist
    return False


def get_general_info(entity_id: str) -> dict | None:
    """
    Get the General Info document for an entity.
    
    Args:
        entity_id: Entity ID
    
    Returns:
        Document dict with content, or None
    """
    md_store = _get_md_store()
    return md_store.get_general_info_document(entity_id)


def search_documents(
    query: str,
    entity_id: str | None = None,
    document_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search documents using full-text search.
    
    This searches the content of ALL documents (General Info, notes, etc.)
    and returns matches with their parent entity information.
    
    Args:
        query: Search query (natural language)
        entity_id: Optional - limit search to documents of this entity
        document_type: Optional - filter by document type (general_info, note, etc.)
        limit: Maximum results
    
    Returns:
        List of matching documents with:
        - id: Document ID
        - name: Document title
        - content_snippet: Matching excerpt
        - parent_entity_id: ID of the entity this doc belongs to
        - parent_entity_name: Name of the parent entity
        - parent_entity_type: Type of parent entity
        - document_type: Type of document
        - relevance_score: Search relevance score
    """
    registry = _get_registry()
    md_store = _get_md_store()
    
    # Search documents
    if entity_id:
        # Search within a specific entity's documents
        all_docs = registry.list_entity_documents(str(entity_id))
        results = []
        query_lower = query.lower()
        
        for doc in all_docs:
            # Check if query matches content or name
            content = doc.get("content", "").lower()
            name = doc.get("name", "").lower()
            
            if query_lower in content or query_lower in name:
                # Get full document content
                full_doc = md_store.read_document(doc["id"])
                
                # Create content snippet around the match
                content_full = full_doc.get("content", "") if full_doc else doc.get("content", "")
                snippet = _create_snippet(content_full, query, max_length=200)
                
                results.append({
                    "id": doc["id"],
                    "name": doc.get("name", "Untitled"),
                    "content_snippet": snippet,
                    "parent_entity_id": doc.get("parent_entity_id"),
                    "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
                    "parent_entity_type": doc.get("parent_entity_type"),
                    "document_type": doc.get("document_type", "note"),
                    "relevance_score": 1.0,
                })
        
        return results[:limit]
    else:
        # Global search using FTS
        search_results = registry.search(query, entity_type="document", limit=limit * 2)
        
        # Filter by document_type if specified
        if document_type:
            search_results = [r for r in search_results if r.get("document_type") == document_type]
        
        results = []
        for doc in search_results[:limit]:
            # Get full document content for snippet
            full_doc = md_store.read_document(doc["id"])
            content_full = full_doc.get("content", "") if full_doc else doc.get("content", "")
            snippet = _create_snippet(content_full, query, max_length=200)
            
            results.append({
                "id": doc["id"],
                "name": doc.get("name", "Untitled"),
                "content_snippet": snippet,
                "parent_entity_id": doc.get("parent_entity_id"),
                "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
                "parent_entity_type": doc.get("parent_entity_type"),
                "document_type": doc.get("document_type", "note"),
                "relevance_score": abs(doc.get("rank", 0)),
            })
        
        return results


def _create_snippet(content: str, query: str, max_length: int = 200) -> str:
    """Create a content snippet around the query match."""
    if not content:
        return ""
    
    query_lower = query.lower()
    content_lower = content.lower()
    
    # Find query position
    pos = content_lower.find(query_lower)
    
    if pos == -1:
        # Query not found exactly, return start of content
        return content[:max_length] + "..." if len(content) > max_length else content
    
    # Center snippet around match
    start = max(0, pos - max_length // 2)
    end = min(len(content), pos + len(query) + max_length // 2)
    
    snippet = content[start:end]
    
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    
    return snippet


def _get_entity_name(entity_id: str | None) -> str | None:
    """Get entity name by ID."""
    if not entity_id:
        return None
    
    registry = _get_registry()
    entity = registry.get(str(entity_id))
    return entity.get("name") if entity else None


__all__ = [
    "append_to_document",
    "get_general_info",
    "search_documents",
]

