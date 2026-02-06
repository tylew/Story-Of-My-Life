"""
MCP Tools - Organizational intelligence tools.

Smart helpers for LLM document management:
- suggest_document_location: Analyze content and suggest best folder + tags
- get_folder_summary: Summarize folder contents for LLM context
- find_organizational_issues: Find problems LLM should address
- suggest_reorganization: Analyze folder and suggest improvements
"""

from datetime import datetime, timedelta
from collections import Counter

from soml.mcp.tools.base import (
    _get_graph_store,
    _get_registry,
    logger,
)


def suggest_document_location(
    content: str,
    title: str | None = None,
    entity_id: str | None = None,
) -> dict:
    """
    Analyze content and suggest best folder + tags.
    
    Uses semantic similarity to existing documents to find
    the most appropriate location and tags.
    
    Args:
        content: Document content to analyze
        title: Optional document title for additional context
        entity_id: Optional - limit suggestions to this entity's folders
    
    Returns:
        Suggestions with:
        - folder_path: Suggested folder path
        - suggested_tags: List of suggested tags
        - similar_documents: Similar existing documents for reference
        - reasoning: Explanation of why these suggestions were made
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    suggestions = {
        "folder_path": "/",
        "suggested_tags": [],
        "similar_documents": [],
        "reasoning": [],
    }
    
    try:
        # 1. Find similar documents using semantic search
        # First, generate embedding for the content
        from soml.mcp.tools.embedding import _generate_embedding_sync
        
        embedding = _generate_embedding_sync(content[:8000])  # Limit content length
        
        if embedding:
            # Search for similar documents in graph
            similar = graph_store.vector_search(
                embedding,
                top_k=5,
                filter_labels=["Document"],
            )
            
            # Collect folder paths and tags from similar docs
            folder_counts = Counter()
            tag_counts = Counter()
            
            for doc in similar:
                doc_id = doc.get("id")
                if doc_id:
                    # Get folder info
                    doc_info = registry.get(doc_id)
                    if doc_info:
                        folder_id = doc_info.get("folder_id")
                        if folder_id:
                            folder_path = registry.get_folder_path(folder_id)
                            folder_counts[folder_path] += doc.get("score", 0.5)
                        
                        suggestions["similar_documents"].append({
                            "id": doc_id,
                            "title": doc_info.get("name", "Untitled"),
                            "similarity": doc.get("score", 0),
                        })
                
                # Get tags from similar doc
                doc_tags = _get_document_tags(doc.get("id"))
                for tag in doc_tags:
                    tag_counts[tag] += doc.get("score", 0.5)
            
            # Most common folder
            if folder_counts:
                best_folder = folder_counts.most_common(1)[0][0]
                suggestions["folder_path"] = best_folder
                suggestions["reasoning"].append(
                    f"Folder '{best_folder}' suggested based on similarity to existing documents"
                )
            
            # Most common tags
            if tag_counts:
                suggestions["suggested_tags"] = [tag for tag, _ in tag_counts.most_common(5)]
                suggestions["reasoning"].append(
                    f"Tags suggested based on similar documents: {', '.join(suggestions['suggested_tags'])}"
                )
        
        # 2. Keyword-based suggestions if no semantic results
        if not suggestions["similar_documents"]:
            # Simple keyword matching against existing folders
            folders = registry.list_folders(owner_entity_id=entity_id)
            content_lower = content.lower()
            
            for folder in folders:
                if folder["name"].lower() in content_lower:
                    folder_path = registry.get_folder_path(folder["id"])
                    suggestions["folder_path"] = folder_path
                    suggestions["reasoning"].append(
                        f"Folder '{folder_path}' matches keyword in content"
                    )
                    break
            
            # Get popular tags
            all_tags = registry.get_all_tags()
            for tag_info in all_tags[:10]:
                tag_name = tag_info["name"]
                if tag_name.lower() in content_lower:
                    suggestions["suggested_tags"].append(tag_name)
            
            if suggestions["suggested_tags"]:
                suggestions["reasoning"].append(
                    f"Tags suggested based on keyword matches"
                )
        
        if not suggestions["reasoning"]:
            suggestions["reasoning"].append(
                "No strong matches found - consider creating a new organizational structure"
            )
        
    except Exception as e:
        logger.warning(f"Error suggesting document location: {e}")
        suggestions["reasoning"].append(f"Analysis limited: {e}")
    
    return suggestions


def get_folder_summary(folder_path: str, entity_id: str | None = None) -> dict:
    """
    Summarize folder contents for LLM context.
    
    Args:
        folder_path: Path of folder to summarize
        entity_id: Optional - entity that owns the folder
    
    Returns:
        Summary with:
        - path: Folder path
        - document_count: Total documents
        - subfolder_count: Number of subfolders
        - document_types: Breakdown by document type
        - recent_activity: Recent documents (last 30 days)
        - tags_used: Common tags in this folder
        - oldest_document: Oldest document info
        - newest_document: Newest document info
    """
    registry = _get_registry()
    
    # Resolve folder
    folder_id = None
    if folder_path and folder_path != "/":
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return {"error": f"Folder not found: {folder_path}"}
        folder_id = folder["id"]
    
    # Get contents
    contents = registry.get_folder_contents(folder_id)
    documents = contents.get("documents", [])
    subfolders = contents.get("folders", [])
    
    # Analyze documents
    type_counts = Counter()
    tags_used = Counter()
    recent_docs = []
    oldest_doc = None
    newest_doc = None
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    for doc in documents:
        # Count types
        doc_type = doc.get("document_type", "note")
        type_counts[doc_type] += 1
        
        # Parse updated_at
        updated_str = doc.get("updated_at")
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                updated_at_naive = updated_at.replace(tzinfo=None)
                
                # Track recent
                if updated_at_naive > thirty_days_ago:
                    recent_docs.append({
                        "id": doc["id"],
                        "name": doc.get("name", "Untitled"),
                        "updated_at": updated_str,
                    })
                
                # Track oldest/newest
                if oldest_doc is None or updated_at_naive < oldest_doc["_date"]:
                    oldest_doc = {
                        "id": doc["id"],
                        "name": doc.get("name", "Untitled"),
                        "updated_at": updated_str,
                        "_date": updated_at_naive,
                    }
                if newest_doc is None or updated_at_naive > newest_doc["_date"]:
                    newest_doc = {
                        "id": doc["id"],
                        "name": doc.get("name", "Untitled"),
                        "updated_at": updated_str,
                        "_date": updated_at_naive,
                    }
            except (ValueError, TypeError):
                pass
        
        # Get tags
        doc_tags = _get_document_tags(doc["id"])
        for tag in doc_tags:
            tags_used[tag] += 1
    
    # Clean up oldest/newest
    if oldest_doc:
        del oldest_doc["_date"]
    if newest_doc:
        del newest_doc["_date"]
    
    return {
        "path": folder_path,
        "document_count": len(documents),
        "subfolder_count": len(subfolders),
        "subfolders": [f["name"] for f in subfolders],
        "document_types": dict(type_counts),
        "recent_activity": recent_docs[:10],
        "tags_used": [{"tag": tag, "count": count} for tag, count in tags_used.most_common(10)],
        "oldest_document": oldest_doc,
        "newest_document": newest_doc,
    }


def find_organizational_issues(entity_id: str | None = None) -> list[dict]:
    """
    Find organizational problems LLM should address.
    
    Identifies:
    - Orphan documents (no folder assignment)
    - Overstuffed folders (>20 documents)
    - Stale documents (not updated in 6+ months)
    - Empty folders
    - Deeply nested folders (>4 levels)
    
    Args:
        entity_id: Optional - limit to this entity's documents/folders
    
    Returns:
        List of issues with:
        - type: Issue type (orphan, overstuffed, stale, empty, deep_nesting)
        - severity: low, medium, high
        - description: Human-readable description
        - affected_items: IDs/paths of affected items
        - suggested_action: What to do about it
    """
    registry = _get_registry()
    issues = []
    
    # 1. Find orphan documents (no folder)
    orphan_docs = _find_orphan_documents(registry, entity_id)
    if orphan_docs:
        issues.append({
            "type": "orphan",
            "severity": "medium",
            "description": f"{len(orphan_docs)} documents without folder assignment",
            "affected_items": orphan_docs[:10],  # Limit for readability
            "suggested_action": "Organize these documents into appropriate folders",
        })
    
    # 2. Find overstuffed folders (>20 documents)
    overstuffed = _find_overstuffed_folders(registry, entity_id, threshold=20)
    for folder_info in overstuffed:
        issues.append({
            "type": "overstuffed",
            "severity": "medium",
            "description": f"Folder '{folder_info['path']}' has {folder_info['count']} documents",
            "affected_items": [folder_info],
            "suggested_action": "Consider splitting into subfolders by theme or date",
        })
    
    # 3. Find stale documents (not updated in 6 months)
    stale_docs = _find_stale_documents(registry, entity_id, days=180)
    if stale_docs:
        issues.append({
            "type": "stale",
            "severity": "low",
            "description": f"{len(stale_docs)} documents not updated in 6+ months",
            "affected_items": stale_docs[:10],
            "suggested_action": "Review for relevance - update, archive, or delete",
        })
    
    # 4. Find empty folders
    empty_folders = _find_empty_folders(registry, entity_id)
    if empty_folders:
        issues.append({
            "type": "empty",
            "severity": "low",
            "description": f"{len(empty_folders)} empty folders",
            "affected_items": empty_folders[:10],
            "suggested_action": "Delete if no longer needed, or add documents",
        })
    
    # 5. Find deeply nested folders (>4 levels)
    deep_folders = _find_deep_folders(registry, entity_id, max_depth=4)
    if deep_folders:
        issues.append({
            "type": "deep_nesting",
            "severity": "low",
            "description": f"{len(deep_folders)} folders nested more than 4 levels deep",
            "affected_items": deep_folders[:5],
            "suggested_action": "Consider flattening folder structure",
        })
    
    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    
    return issues


def suggest_reorganization(folder_path: str, entity_id: str | None = None) -> dict:
    """
    Analyze folder and suggest improvements.
    
    Analyzes:
    - Document themes for potential subfolders
    - Similar folders that could be merged
    - Documents that might belong elsewhere
    
    Args:
        folder_path: Path of folder to analyze
        entity_id: Optional - entity that owns the folder
    
    Returns:
        Suggestions with:
        - current_state: Summary of current folder
        - suggested_subfolders: Themes that could become subfolders
        - merge_candidates: Similar folders that could be combined
        - misplaced_documents: Docs that might belong elsewhere
        - summary: Overall recommendation
    """
    registry = _get_registry()
    graph_store = _get_graph_store()
    
    # Resolve folder
    folder_id = None
    if folder_path and folder_path != "/":
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return {"error": f"Folder not found: {folder_path}"}
        folder_id = folder["id"]
    
    # Get folder contents
    contents = registry.get_folder_contents(folder_id)
    documents = contents.get("documents", [])
    subfolders = contents.get("folders", [])
    
    result = {
        "current_state": {
            "path": folder_path,
            "document_count": len(documents),
            "subfolder_count": len(subfolders),
        },
        "suggested_subfolders": [],
        "merge_candidates": [],
        "misplaced_documents": [],
        "summary": "",
    }
    
    # Analyze document tags to find themes
    tag_to_docs = {}
    for doc in documents:
        tags = _get_document_tags(doc["id"])
        for tag in tags:
            if tag not in tag_to_docs:
                tag_to_docs[tag] = []
            tag_to_docs[tag].append({
                "id": doc["id"],
                "name": doc.get("name", "Untitled"),
            })
    
    # Suggest subfolders for tags with 3+ documents
    for tag, docs in tag_to_docs.items():
        if len(docs) >= 3:
            result["suggested_subfolders"].append({
                "name": tag,
                "document_count": len(docs),
                "documents": docs[:5],  # Sample
                "reason": f"{len(docs)} documents share the '{tag}' tag",
            })
    
    # Look for similar sibling folders that could be merged
    if folder_id:
        parent_folder = registry.get_folder(folder_id)
        parent_id = parent_folder.get("parent_folder_id") if parent_folder else None
    else:
        parent_id = None
    
    siblings = registry.list_folders(parent_folder_id=parent_id, owner_entity_id=entity_id)
    folder_name = folder_path.split("/")[-1].lower() if folder_path else ""
    
    for sibling in siblings:
        sibling_name = sibling["name"].lower()
        if sibling_name != folder_name and _names_similar(folder_name, sibling_name):
            sibling_path = registry.get_folder_path(sibling["id"])
            sibling_contents = registry.get_folder_contents(sibling["id"])
            result["merge_candidates"].append({
                "path": sibling_path,
                "document_count": len(sibling_contents.get("documents", [])),
                "reason": f"Similar name to current folder",
            })
    
    # Build summary
    summaries = []
    if len(documents) > 20:
        summaries.append("Folder is large and could benefit from subfolders")
    if result["suggested_subfolders"]:
        summaries.append(f"Found {len(result['suggested_subfolders'])} potential themes for subfolders")
    if result["merge_candidates"]:
        summaries.append(f"Found {len(result['merge_candidates'])} similar folders to potentially merge")
    if not summaries:
        summaries.append("Folder appears well-organized")
    
    result["summary"] = ". ".join(summaries) + "."
    
    return result


# ============================================
# Helper Functions
# ============================================

def _get_document_tags(doc_id: str) -> list[str]:
    """Get tags for a document from the graph."""
    try:
        graph_store = _get_graph_store()
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


def _find_orphan_documents(registry, entity_id: str | None) -> list[dict]:
    """Find documents without folder assignment."""
    with registry._get_connection() as conn:
        if entity_id:
            rows = conn.execute(
                """
                SELECT id, name FROM documents 
                WHERE folder_id IS NULL AND parent_entity_id = ?
                ORDER BY updated_at DESC
                """,
                (entity_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name FROM documents 
                WHERE folder_id IS NULL
                ORDER BY updated_at DESC
                """
            ).fetchall()
        
        return [{"id": row["id"], "name": row["name"]} for row in rows]


def _find_overstuffed_folders(registry, entity_id: str | None, threshold: int = 20) -> list[dict]:
    """Find folders with more than threshold documents."""
    folders = registry.list_folders(owner_entity_id=entity_id)
    result = []
    
    for folder in folders:
        contents = registry.get_folder_contents(folder["id"])
        doc_count = len(contents.get("documents", []))
        if doc_count > threshold:
            result.append({
                "id": folder["id"],
                "path": registry.get_folder_path(folder["id"]),
                "count": doc_count,
            })
    
    return result


def _find_stale_documents(registry, entity_id: str | None, days: int = 180) -> list[dict]:
    """Find documents not updated in specified days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    with registry._get_connection() as conn:
        if entity_id:
            rows = conn.execute(
                """
                SELECT id, name, updated_at FROM documents 
                WHERE updated_at < ? AND parent_entity_id = ?
                ORDER BY updated_at ASC
                """,
                (cutoff, entity_id)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, updated_at FROM documents 
                WHERE updated_at < ?
                ORDER BY updated_at ASC
                """,
                (cutoff,)
            ).fetchall()
        
        return [
            {"id": row["id"], "name": row["name"], "last_updated": row["updated_at"]}
            for row in rows
        ]


def _find_empty_folders(registry, entity_id: str | None) -> list[dict]:
    """Find folders with no documents or subfolders."""
    folders = registry.list_folders(owner_entity_id=entity_id)
    result = []
    
    for folder in folders:
        contents = registry.get_folder_contents(folder["id"])
        if not contents.get("documents") and not contents.get("folders"):
            result.append({
                "id": folder["id"],
                "path": registry.get_folder_path(folder["id"]),
            })
    
    return result


def _find_deep_folders(registry, entity_id: str | None, max_depth: int = 4) -> list[dict]:
    """Find folders nested deeper than max_depth."""
    folders = registry.list_folders(owner_entity_id=entity_id)
    result = []
    
    for folder in folders:
        path = registry.get_folder_path(folder["id"])
        depth = path.count("/")
        if depth > max_depth:
            result.append({
                "id": folder["id"],
                "path": path,
                "depth": depth,
            })
    
    return result


def _names_similar(name1: str, name2: str) -> bool:
    """Check if two folder names are similar enough to consider merging."""
    if not name1 or not name2:
        return False
    
    # Simple heuristics
    # 1. One contains the other
    if name1 in name2 or name2 in name1:
        return True
    
    # 2. Similar prefix (first 5 chars)
    if len(name1) >= 5 and len(name2) >= 5:
        if name1[:5] == name2[:5]:
            return True
    
    # 3. Levenshtein-like - count matching characters
    shorter, longer = (name1, name2) if len(name1) <= len(name2) else (name2, name1)
    matches = sum(1 for c in shorter if c in longer)
    if matches / len(shorter) > 0.8:
        return True
    
    return False


__all__ = [
    "suggest_document_location",
    "get_folder_summary",
    "find_organizational_issues",
    "suggest_reorganization",
]

