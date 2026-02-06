"""
MCP Tools - Document management tools.

Tools for managing documents:
- search_documents: Semantic + keyword search across documents
- find_related_documents: Find docs sharing tags or referencing an entity
- find_documents_needing_update: Find stale docs on a topic
- create_document: Create new document with organization options
- update_document: Update document content and/or metadata
- move_document: Move document to different folder
- delete_document: Delete document from all stores
- append_to_document: Append content to General Info
- get_general_info: Get General Info document for an entity
"""

from datetime import datetime
from uuid import UUID, uuid4

from soml.core.types import Document, DocumentType, EntityType, Source
from soml.mcp.tools.base import (
    _get_audit,
    _get_graph_store,
    _get_md_store,
    _get_registry,
    logger,
)


def search_documents(
    query: str,
    entity_id: str | None = None,
    folder_path: str | None = None,
    tags: list[str] | None = None,
    document_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search documents using semantic + keyword search with filters.
    
    This searches the content of ALL documents (General Info, notes, etc.)
    and returns matches with their parent entity information.
    
    Args:
        query: Search query (natural language)
        entity_id: Optional - limit search to documents of this entity
        folder_path: Optional - limit search to documents in this folder path
        tags: Optional - filter by documents with ALL these tags
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
        - folder_path: Path of the containing folder
        - tags: Document tags
        - relevance_score: Search relevance score
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # If tags specified, use graph to find docs with those tags first
    if tags:
        tag_filtered_ids = set()
        for tag in tags:
            items = graph_store.find_by_tag(tag, include_entities=False, include_documents=True)
            doc_ids = {item["id"] for item in items if item.get("item_type") == "document"}
            if not tag_filtered_ids:
                tag_filtered_ids = doc_ids
            else:
                tag_filtered_ids &= doc_ids  # Intersection - must have ALL tags
        
        if not tag_filtered_ids:
            return []  # No docs have all tags
    else:
        tag_filtered_ids = None
    
    # If folder_path specified, get folder and list its documents
    if folder_path:
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return []
        folder_contents = registry.get_folder_contents(folder["id"])
        folder_doc_ids = {doc["id"] for doc in folder_contents.get("documents", [])}
        
        if tag_filtered_ids is not None:
            tag_filtered_ids &= folder_doc_ids
        else:
            tag_filtered_ids = folder_doc_ids
    
    # Now do text search
    if entity_id:
        # Search within a specific entity's documents
        all_docs = registry.list_entity_documents(str(entity_id))
        results = []
        query_lower = query.lower()
        
        for doc in all_docs:
            # Apply tag filter if set
            if tag_filtered_ids is not None and doc["id"] not in tag_filtered_ids:
                continue
            
            # Check if query matches content or name
            content = doc.get("content", "").lower()
            name = doc.get("name", "").lower()
            
            if query_lower in content or query_lower in name:
                # Get full document content
                full_doc = md_store.read_document(doc["id"])
                
                # Create content snippet around the match
                content_full = full_doc.get("content", "") if full_doc else doc.get("content", "")
                snippet = _create_snippet(content_full, query, max_length=200)
                
                # Get folder path
                folder_id = doc.get("folder_id")
                doc_folder_path = registry.get_folder_path(folder_id) if folder_id else "/"
                
                results.append({
                    "id": doc["id"],
                    "name": doc.get("name", "Untitled"),
                    "content_snippet": snippet,
                    "parent_entity_id": doc.get("parent_entity_id"),
                    "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
                    "parent_entity_type": doc.get("parent_entity_type"),
                    "document_type": doc.get("document_type", "note"),
                    "folder_path": doc_folder_path,
                    "tags": _get_document_tags(doc["id"]),
                    "relevance_score": 1.0,
                })
        
        return results[:limit]
    else:
        # Global search using FTS
        search_results = registry.search(query, entity_type="document", limit=limit * 2)
        
        # Filter by document_type if specified
        if document_type:
            search_results = [r for r in search_results if r.get("document_type") == document_type]
        
        # Apply tag filter
        if tag_filtered_ids is not None:
            search_results = [r for r in search_results if r["id"] in tag_filtered_ids]
        
        results = []
        for doc in search_results[:limit]:
            # Get full document content for snippet
            full_doc = md_store.read_document(doc["id"])
            content_full = full_doc.get("content", "") if full_doc else doc.get("content", "")
            snippet = _create_snippet(content_full, query, max_length=200)
            
            # Get folder path
            folder_id = doc.get("folder_id")
            doc_folder_path = registry.get_folder_path(folder_id) if folder_id else "/"
            
            results.append({
                "id": doc["id"],
                "name": doc.get("name", "Untitled"),
                "content_snippet": snippet,
                "parent_entity_id": doc.get("parent_entity_id"),
                "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
                "parent_entity_type": doc.get("parent_entity_type"),
                "document_type": doc.get("document_type", "note"),
                "folder_path": doc_folder_path,
                "tags": _get_document_tags(doc["id"]),
                "relevance_score": abs(doc.get("rank", 0)),
            })
        
        return results


def find_related_documents(entity_id: str) -> list[dict]:
    """
    Find documents related to an entity.
    
    Returns documents that:
    - Share tags with the entity
    - Reference the entity via wikilinks
    - Belong to related entities
    
    Args:
        entity_id: Entity ID to find related documents for
    
    Returns:
        List of related documents with:
        - id: Document ID
        - name: Document title
        - relation_type: How this doc is related (shared_tag, references, related_entity)
        - shared_tags: Tags shared with the entity (if applicable)
        - parent_entity_id: Parent entity of the document
        - parent_entity_name: Name of parent entity
    """
    graph_store = _get_graph_store()
    registry = _get_registry()
    
    results = []
    seen_ids = set()
    
    # 1. Documents that reference this entity
    referencing_docs = graph_store.find_documents_referencing(entity_id)
    for doc in referencing_docs:
        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            results.append({
                "id": doc["id"],
                "name": doc.get("title", "Untitled"),
                "relation_type": "references",
                "shared_tags": [],
                "parent_entity_id": doc.get("parent_entity_id"),
                "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
            })
    
    # 2. Documents sharing tags with this entity
    related_by_tags = graph_store.find_related_by_tags(entity_id)
    for item in related_by_tags:
        if item.get("item_type") == "document" and item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            results.append({
                "id": item["id"],
                "name": item.get("title") or item.get("name", "Untitled"),
                "relation_type": "shared_tag",
                "shared_tags": item.get("shared_tags", []),
                "parent_entity_id": item.get("parent_entity_id"),
                "parent_entity_name": _get_entity_name(item.get("parent_entity_id")),
            })
    
    # 3. Documents of this entity itself
    entity_docs = graph_store.find_documents_for_entity(entity_id)
    for doc in entity_docs:
        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            results.append({
                "id": doc["id"],
                "name": doc.get("title", "Untitled"),
                "relation_type": "belongs_to",
                "shared_tags": [],
                "parent_entity_id": entity_id,
                "parent_entity_name": _get_entity_name(entity_id),
            })
    
    return results


def find_documents_needing_update(topic: str, days_old: int = 180) -> list[dict]:
    """
    Find documents mentioning a topic that may need refresh.
    
    Identifies documents that:
    - Mention the topic in content
    - Haven't been updated in the specified time period
    
    Args:
        topic: Topic keyword to search for
        days_old: Consider documents older than this many days as potentially stale
    
    Returns:
        List of potentially stale documents with:
        - id: Document ID
        - name: Document title
        - last_updated: When document was last updated
        - days_since_update: Number of days since last update
        - content_snippet: Excerpt containing the topic
    """
    registry = _get_registry()
    md_store = _get_md_store()
    
    # Search for documents mentioning the topic
    search_results = registry.search(topic, entity_type="document", limit=100)
    
    cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    results = []
    
    for doc in search_results:
        updated_str = doc.get("updated_at")
        if not updated_str:
            continue
        
        try:
            updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            days_since = (cutoff_date - updated_at.replace(tzinfo=None)).days
            
            if days_since >= days_old:
                # Get content snippet
                full_doc = md_store.read_document(doc["id"])
                content = full_doc.get("content", "") if full_doc else ""
                snippet = _create_snippet(content, topic, max_length=200)
                
                results.append({
                    "id": doc["id"],
                    "name": doc.get("name", "Untitled"),
                    "last_updated": updated_str,
                    "days_since_update": days_since,
                    "content_snippet": snippet,
                    "parent_entity_id": doc.get("parent_entity_id"),
                    "parent_entity_name": _get_entity_name(doc.get("parent_entity_id")),
                })
        except (ValueError, TypeError):
            continue
    
    # Sort by oldest first
    results.sort(key=lambda x: x["days_since_update"], reverse=True)
    return results


def create_document(
    title: str,
    content: str,
    folder_path: str | None = None,
    parent_entity_id: str | None = None,
    parent_relationship_id: str | None = None,
    tags: list[str] | None = None,
    document_type: str = "note",
) -> dict:
    """
    Create new document with full organization options.
    
    Syncs to markdown file, registry, and graph.
    
    Args:
        title: Document title
        content: Document content (markdown)
        folder_path: Optional folder path (e.g., "/projects/acme")
        parent_entity_id: Optional parent entity ID
        parent_relationship_id: Optional parent relationship ID
        tags: Optional list of tags
        document_type: Type of document (note, general_info, etc.)
    
    Returns:
        Created document info with:
        - id: Document ID
        - title: Document title
        - path: File path
        - folder_path: Folder path
        - tags: Applied tags
        - success: Whether creation succeeded
        - error: Error message if failed
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    doc_id = uuid4()
    
    try:
        # Resolve folder if specified
        folder_id = None
        if folder_path and folder_path != "/":
            folder = registry.get_folder_by_path(folder_path, parent_entity_id)
            if folder:
                folder_id = folder["id"]
            else:
                # Create the folder path
                folder_id = _ensure_folder_path(folder_path, parent_entity_id, registry)
        
        # Map document_type string to enum
        doc_type_enum = DocumentType.NOTE
        if document_type == "general_info":
            doc_type_enum = DocumentType.GENERAL_INFO
        elif document_type == "meeting_notes":
            doc_type_enum = DocumentType.MEETING_NOTES
        elif document_type == "journal":
            doc_type_enum = DocumentType.JOURNAL
        
        # Create document object
        doc = Document(
            id=doc_id,
            title=title,
            document_type=doc_type_enum,
            content=content,
            parent_entity_id=UUID(parent_entity_id) if parent_entity_id else None,
            parent_entity_type=_get_entity_type(parent_entity_id) if parent_entity_id else None,
            tags=tags or [],
            source=Source.AGENT,
            last_edited_by=Source.AGENT,
        )
        
        # Write to markdown
        filepath = md_store.write_document(doc)
        
        # Index in registry
        registry.index(
            doc_id=str(doc_id),
            path=filepath,
            entity_type=EntityType.DOCUMENT,
            name=title,
            checksum=md_store._compute_checksum(content),
            content=content,
            tags=tags,
            document_type=document_type,
            parent_entity_id=parent_entity_id,
            parent_entity_type=_get_entity_type(parent_entity_id).value if parent_entity_id else None,
            parent_relationship_id=parent_relationship_id,
        )
        
        # Update folder_id in registry
        if folder_id:
            registry.update_document_folder(str(doc_id), folder_id)
        
        # Create document node in graph
        graph_store.upsert_document_node(
            doc_id=str(doc_id),
            title=title,
            doc_type=document_type,
            parent_entity_id=parent_entity_id,
            parent_relationship_id=parent_relationship_id,
        )
        
        # Sync tags to graph
        if tags:
            graph_store.sync_item_tags(str(doc_id), "document", tags)
        
        # Parse wikilinks and create references
        referenced_ids = _extract_wikilink_ids(content)
        if referenced_ids:
            graph_store.sync_document_references(str(doc_id), referenced_ids)
        
        # Audit log
        audit = _get_audit()
        audit.log_create(
            document_id=str(doc_id),
            data={"title": title, "document_type": document_type, "content": content[:500], "tags": tags or []},
            actor="agent",
            item_type="document",
            item_name=title,
        )
        
        logger.info(f"Created document '{title}' ({doc_id})")
        
        return {
            "id": str(doc_id),
            "title": title,
            "path": str(filepath),
            "folder_path": folder_path or "/",
            "tags": tags or [],
            "success": True,
        }
        
    except Exception as e:
        logger.error(f"Failed to create document '{title}': {e}")
        return {
            "id": None,
            "title": title,
            "path": None,
            "folder_path": folder_path,
            "tags": tags,
            "success": False,
            "error": str(e),
        }


def update_document(
    doc_id: str,
    content: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    mode: str = "append",
) -> dict:
    """
    Update document content and/or metadata.
    
    Args:
        doc_id: Document ID
        content: New content (if mode='replace') or content to append (if mode='append')
        title: New title (optional)
        tags: New tags (replaces existing, optional)
        mode: 'append' to add content, 'replace' to overwrite content
    
    Returns:
        Update result with:
        - success: Whether update succeeded
        - id: Document ID
        - changes: List of what was changed
        - error: Error message if failed
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    audit = _get_audit()
    
    changes = []
    
    try:
        # Get existing document
        doc = md_store.read_document(doc_id)
        if not doc:
            return {
                "success": False,
                "id": doc_id,
                "changes": [],
                "error": f"Document {doc_id} not found",
            }
        
        # Capture before-state for audit
        old_content = doc.get("content", "")
        old_title = doc.get("metadata", {}).get("title", "")
        
        # Update content
        if content:
            if mode == "append":
                success = md_store.append_to_document(doc_id, content, Source.AGENT)
                if success:
                    changes.append("appended_content")
                    
                    # Re-parse wikilinks
                    full_doc = md_store.read_document(doc_id)
                    if full_doc:
                        referenced_ids = _extract_wikilink_ids(full_doc.get("content", ""))
                        graph_store.sync_document_references(doc_id, referenced_ids)
            else:
                # Replace mode - rewrite the document
                existing_metadata = doc.get("metadata", {})
                new_doc = Document(
                    id=UUID(doc_id),
                    title=title or existing_metadata.get("title", "Untitled"),
                    document_type=DocumentType(existing_metadata.get("document_type", "note")),
                    content=content,
                    parent_entity_id=UUID(existing_metadata["parent_entity_id"]) if existing_metadata.get("parent_entity_id") else None,
                    parent_entity_type=EntityType(existing_metadata["parent_entity_type"]) if existing_metadata.get("parent_entity_type") else None,
                    tags=tags if tags is not None else existing_metadata.get("tags", []),
                    source=Source.AGENT,
                    last_edited_by=Source.AGENT,
                )
                md_store.write_document(new_doc)
                changes.append("replaced_content")
                
                # Update registry
                registry.index(
                    doc_id=doc_id,
                    path=registry.get(doc_id)["path"],
                    entity_type=EntityType.DOCUMENT,
                    name=new_doc.title,
                    checksum=md_store._compute_checksum(content),
                    content=content,
                    tags=new_doc.tags,
                    document_type=new_doc.document_type.value,
                    parent_entity_id=str(new_doc.parent_entity_id) if new_doc.parent_entity_id else None,
                    parent_entity_type=new_doc.parent_entity_type.value if new_doc.parent_entity_type else None,
                )
                
                # Parse and sync wikilinks
                referenced_ids = _extract_wikilink_ids(content)
                graph_store.sync_document_references(doc_id, referenced_ids)
        
        # Update title only (if no content change)
        elif title:
            # TODO: Implement title-only update (requires renaming file)
            changes.append("title_change_pending")
        
        # Update tags
        if tags is not None:
            graph_store.sync_item_tags(doc_id, "document", tags)
            changes.append("updated_tags")
        
        # Audit log with content snapshot
        if changes:
            updated_doc = md_store.read_document(doc_id)
            audit.log_update(
                document_id=doc_id,
                old_data={"title": old_title, "content": old_content},
                new_data={"title": title or old_title, "content": updated_doc.get("content", "") if updated_doc else ""},
                actor="agent",
                item_type="document",
                item_name=title or old_title,
            )
        
        logger.info(f"Updated document {doc_id}: {changes}")
        
        return {
            "success": True,
            "id": doc_id,
            "changes": changes,
        }
        
    except Exception as e:
        logger.error(f"Failed to update document {doc_id}: {e}")
        return {
            "success": False,
            "id": doc_id,
            "changes": changes,
            "error": str(e),
        }


def move_document(doc_id: str, new_folder_path: str) -> dict:
    """
    Move document to a different folder.
    
    Args:
        doc_id: Document ID
        new_folder_path: Target folder path (e.g., "/projects/acme")
    
    Returns:
        Move result with:
        - success: Whether move succeeded
        - id: Document ID
        - old_folder_path: Previous folder path
        - new_folder_path: New folder path
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Get current document info
        doc = registry.get(doc_id)
        if not doc:
            return {
                "success": False,
                "id": doc_id,
                "old_folder_path": None,
                "new_folder_path": new_folder_path,
                "error": f"Document {doc_id} not found",
            }
        
        old_folder_id = doc.get("folder_id")
        old_folder_path = registry.get_folder_path(old_folder_id) if old_folder_id else "/"
        
        # Resolve new folder
        parent_entity_id = doc.get("parent_entity_id")
        new_folder_id = None
        
        if new_folder_path and new_folder_path != "/":
            folder = registry.get_folder_by_path(new_folder_path, parent_entity_id)
            if folder:
                new_folder_id = folder["id"]
            else:
                # Create the folder path
                new_folder_id = _ensure_folder_path(new_folder_path, parent_entity_id, registry)
        
        # Update folder_id
        registry.update_document_folder(doc_id, new_folder_id)
        
        logger.info(f"Moved document {doc_id} from '{old_folder_path}' to '{new_folder_path}'")
        
        return {
            "success": True,
            "id": doc_id,
            "old_folder_path": old_folder_path,
            "new_folder_path": new_folder_path,
        }
        
    except Exception as e:
        logger.error(f"Failed to move document {doc_id}: {e}")
        return {
            "success": False,
            "id": doc_id,
            "old_folder_path": None,
            "new_folder_path": new_folder_path,
            "error": str(e),
        }


def delete_document(doc_id: str, hard: bool = False) -> dict:
    """
    Delete document from all stores (markdown, registry, graph).
    
    Soft delete by default: moves markdown to .deleted/ for recovery.
    
    Args:
        doc_id: Document ID
        hard: If True, permanently delete. If False (default), soft delete.
    
    Returns:
        Delete result with:
        - success: Whether delete succeeded
        - id: Document ID
        - error: Error message if failed
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    audit = _get_audit()
    
    try:
        # Get document info
        doc = registry.get(doc_id)
        if not doc:
            return {
                "success": False,
                "id": doc_id,
                "error": f"Document {doc_id} not found in registry",
            }
        
        # Capture full snapshot for audit (enables undo)
        md_doc = md_store.read_document(doc_id)
        doc_snapshot = {
            "registry": doc,
            "content": md_doc.get("content", "") if md_doc else "",
            "metadata": md_doc.get("metadata", {}) if md_doc else {},
            "filepath": doc.get("path", ""),
        }
        
        filepath = doc.get("path")
        
        # Delete from graph (removes node, edges, and vector embedding)
        graph_store.delete_document_node(doc_id)
        
        # Delete from registry
        registry.delete(doc_id)
        
        # Delete/soft-delete markdown file
        if filepath:
            from pathlib import Path
            path = Path(filepath)
            if path.exists():
                md_store.delete(path, soft=not hard)
                logger.info(f"{'Soft' if not hard else 'Hard'} deleted document file: {filepath}")
        
        # Audit log
        audit.log_delete(
            document_id=doc_id,
            data=doc_snapshot,
            soft=not hard,
            actor="agent",
            item_type="document",
            item_name=doc.get("name", "Document"),
        )
        
        logger.info(f"Deleted document {doc_id}")
        
        return {
            "success": True,
            "id": doc_id,
            "soft_delete": not hard,
        }
        
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return {
            "success": False,
            "id": doc_id,
            "error": str(e),
        }


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


# ============================================
# Helper Functions
# ============================================

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


def _get_entity_type(entity_id: str | None) -> EntityType | None:
    """Get entity type by ID."""
    if not entity_id:
        return None
    
    registry = _get_registry()
    entity = registry.get(str(entity_id))
    if entity:
        type_str = entity.get("type")
        if type_str:
            try:
                return EntityType(type_str)
            except ValueError:
                pass
    return None


def _get_document_tags(doc_id: str) -> list[str]:
    """Get tags for a document from the graph."""
    try:
        graph_store = _get_graph_store()
        # Query graph for document's tags
        with graph_store.session() as session:
            result = session.run(
                """
                MATCH (d:Document {id: $doc_id})-[:HAS_TAG]->(t:Tag)
                RETURN t.name as tag
                """,
                doc_id=doc_id
            )
            return [record["tag"] for record in result]
    except Exception:
        return []


def _extract_wikilink_ids(content: str) -> list[str]:
    """Extract entity IDs from wikilinks in content."""
    import re
    # Match [[id|display]] or [[id]]
    pattern = r'\[\[([a-f0-9-]{36})\|?[^\]]*\]\]'
    matches = re.findall(pattern, content)
    return list(set(matches))


def _ensure_folder_path(folder_path: str, owner_entity_id: str | None, registry) -> str | None:
    """Ensure all folders in a path exist, creating if needed. Returns final folder ID."""
    if not folder_path or folder_path == "/":
        return None
    
    parts = [p for p in folder_path.strip("/").split("/") if p]
    if not parts:
        return None
    
    parent_id = None
    for part in parts:
        # Check if folder exists
        existing = registry.list_folders(parent_folder_id=parent_id, owner_entity_id=owner_entity_id)
        folder = next((f for f in existing if f["name"] == part), None)
        
        if folder:
            parent_id = folder["id"]
        else:
            # Create folder
            folder_id = registry.create_folder(
                name=part,
                parent_folder_id=parent_id,
                owner_entity_id=owner_entity_id,
            )
            parent_id = folder_id
    
    return parent_id


__all__ = [
    # Search and discovery
    "search_documents",
    "find_related_documents",
    "find_documents_needing_update",
    # CRUD operations
    "create_document",
    "update_document",
    "move_document",
    "delete_document",
    # Legacy/compatibility
    "append_to_document",
    "get_general_info",
]
