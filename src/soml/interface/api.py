"""
FastAPI backend for the Story of My Life UI.

Provides REST endpoints for:
- Graph data retrieval
- Entity browsing
- Chat interface (via CrewAI)
- Timeline queries

This is a simplified API that delegates to CrewAI + MCP tools.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from soml.core.config import Settings, get_logger
from soml.core.types import EntityType, DocumentType, Document, Period, Source
from soml.crew.crew import SOMLCrew, get_crew
from soml.storage.conversations import ConversationStore

logger = get_logger("api")
from soml.storage.graph import GraphStore
from soml.storage.registry import RegistryStore
from soml.storage.markdown import MarkdownStore

# Initialize app
app = FastAPI(
    title="Story of My Life API",
    description="Personal knowledge graph API",
    version="0.2.0",  # Version bump for CrewAI integration
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
settings = Settings()
graph_store = GraphStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
registry = RegistryStore()
md_store = MarkdownStore()
conv_store = ConversationStore()


@app.on_event("startup")
async def startup_event():
    """Initialize database indexes on startup."""
    try:
        graph_store.ensure_indexes()
        logger.info("Database indexes initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize some indexes (may already exist): {e}")

# CrewAI orchestrator (lazy loaded)
_crew: SOMLCrew | None = None

def get_crew_instance() -> SOMLCrew:
    """Get or create the CrewAI orchestrator."""
    global _crew
    if _crew is None:
        _crew = SOMLCrew()
    return _crew


# ==========================================
# Request/Response Models
# ==========================================

class ChatMessage(BaseModel):
    message: str
    
class AddNoteRequest(BaseModel):
    content: str

class ConversationRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    context: list[dict] | None = None

class ProposalConfirmRequest(BaseModel):
    conversation_id: str
    proposal_set_id: str
    entity_selections: dict[str, str | None] = {}  # proposal_id -> selected_candidate_id or "new"
    entity_descriptions: dict[str, str] = {}  # proposal_id -> description for new entities
    relationship_approvals: dict[str, bool] = {}  # proposal_id -> approved
    document_approvals: dict[str, bool] = {}  # proposal_id -> approved


class UpdateConversationRequest(BaseModel):
    name: str | None = None


class GraphData(BaseModel):
    nodes: list[dict]
    edges: list[dict]

class CreateDocumentRequest(BaseModel):
    title: str
    content: str = ""
    document_type: str = "custom"
    parent_entity_id: str | None = None
    parent_entity_type: str | None = None

class UpdateDocumentRequest(BaseModel):
    title: str | None = None
    content: str | None = None

class AppendDocumentRequest(BaseModel):
    content: str
    section: str | None = None

class UpdateEntityRequest(BaseModel):
    """Request to update an entity's editable properties."""
    # Type-specific fields (will vary by entity type)
    name: str | None = None
    title: str | None = None
    disambiguator: str | None = None
    email: str | None = None
    phone: str | None = None
    current_employer: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    target_date: str | None = None
    progress: int | None = None
    on_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    # Common fields
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None

# Conversation store is now in SQLite (ConversationStore)


# ==========================================
# Health & Status
# ==========================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def status():
    """Get system status."""
    counts = {}
    for entity_type in ["person", "project", "goal", "event", "note", "period"]:
        try:
            docs = registry.list_by_type(entity_type)
            counts[entity_type] = len(docs)
        except:
            counts[entity_type] = 0
    
    return {
        "status": "connected",
        "counts": counts,
        "neo4j": settings.neo4j_uri,
        "data_dir": str(settings.data_dir),
    }


# ==========================================
# Admin / Maintenance Endpoints
# ==========================================

@app.post("/admin/refresh-embeddings")
async def refresh_embeddings(entity_type: str | None = None, background: bool = True):
    """
    Regenerate embeddings for all entities (or entities of a specific type).
    
    This is a maintenance operation to embed existing documents that 
    were created before the embedding system was implemented.
    
    Args:
        entity_type: Optional filter (person, project, goal, event, period)
        background: If true (default), run in background and return immediately
    
    Returns:
        Stats if run synchronously, or job status if background
    """
    from soml.mcp import tools as mcp_tools
    import threading
    
    if background:
        def run_refresh():
            try:
                stats = mcp_tools.refresh_all_embeddings(entity_type)
                logger.info(f"Background embedding refresh complete: {stats}")
            except Exception as e:
                logger.error(f"Background embedding refresh failed: {e}")
        
        thread = threading.Thread(target=run_refresh, daemon=True)
        thread.start()
        
        return {
            "status": "started",
            "message": f"Embedding refresh started in background for {'all entities' if not entity_type else entity_type + ' entities'}",
        }
    else:
        # Run synchronously (may take a while)
        stats = mcp_tools.refresh_all_embeddings(entity_type)
        return {
            "status": "complete",
            "stats": stats,
        }


@app.post("/admin/refresh-embedding/{entity_id}")
async def refresh_single_embedding(entity_id: str):
    """
    Regenerate embedding for a single entity.
    
    Use this after updating an entity's content to refresh its embedding.
    """
    from soml.mcp import tools as mcp_tools
    
    success = mcp_tools.generate_and_store_embedding(entity_id)
    
    if success:
        return {"status": "success", "message": f"Embedding refreshed for {entity_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")


# ==========================================
# Graph Endpoints
# ==========================================

@app.get("/graph")
async def get_graph() -> GraphData:
    """Get full graph data for visualization."""
    nodes = []
    edges = []
    
    # Get all entities from registry
    entity_types = [
        EntityType.PERSON,
        EntityType.PROJECT, 
        EntityType.GOAL,
        EntityType.EVENT,
        EntityType.PERIOD,
    ]
    
    for entity_type in entity_types:
        docs = registry.list_by_type(entity_type)
        for doc in docs:
            nodes.append({
                "id": doc.get("id"),
                "label": doc.get("name") or doc.get("title", "Unknown"),
                "type": doc.get("type"),
                "group": doc.get("type"),
            })
    
    # Get relationships from Neo4j
    try:
        with graph_store.session() as session:
            result = session.run("""
                MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
                RETURN a.id as source, b.id as target, r.type as type
                LIMIT 500
            """)
            for record in result:
                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"] or "related",
                })
    except Exception as e:
        print(f"Error fetching relationships: {e}")
    
    return GraphData(nodes=nodes, edges=edges)


@app.get("/graph/node/{node_id}")
async def get_node(node_id: str):
    """Get details for a specific node."""
    # Try to find in registry first (for basic info)
    registry_doc = registry.get(node_id)
    if not registry_doc:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Get full entity data from markdown file (has all frontmatter fields)
    md_doc = md_store.read_by_id(node_id, registry_doc.get("type"))
    
    if md_doc:
        # Return frontmatter metadata (has custom_fields, tags, etc.)
        metadata = md_doc.get("metadata", {})
        content = md_doc.get("content", "")
    else:
        # Fallback to registry data
        metadata = registry_doc
        content = ""
    
    # Get relationships
    relationships = graph_store.get_relationships(node_id)
    
    return {
        "id": node_id,
        "metadata": metadata,
        "content": content,
        "relationships": relationships,
    }


# ==========================================
# Entity Endpoints
# ==========================================

@app.get("/entities/{entity_type}")
async def list_entities(entity_type: str):
    """List all entities of a given type."""
    try:
        docs = registry.list_by_type(entity_type)
        return {"entities": docs, "count": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/people")
async def list_people():
    """List all people."""
    docs = registry.list_by_type(EntityType.PERSON)
    return {"people": docs, "count": len(docs)}


@app.get("/projects")
async def list_projects():
    """List all projects."""
    docs = registry.list_by_type(EntityType.PROJECT)
    return {"projects": docs, "count": len(docs)}


@app.get("/goals")
async def list_goals():
    """List all goals."""
    docs = registry.list_by_type(EntityType.GOAL)
    return {"goals": docs, "count": len(docs)}


@app.get("/events")
async def list_events():
    """List all events."""
    docs = registry.list_by_type(EntityType.EVENT)
    return {"events": docs, "count": len(docs)}


@app.get("/notes")
async def list_notes():
    """List all notes."""
    docs = registry.list_by_type(EntityType.NOTE)
    return {"notes": docs, "count": len(docs)}


@app.get("/entities/detail/{entity_id}")
async def get_entity_detail(entity_id: str):
    """Get full entity details including metadata, content, and custom_fields."""
    try:
        # Get from registry
        entity = registry.get(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_type = entity.get("type")
        
        # Read full markdown file
        md_doc = md_store.read_by_id(entity_id, entity_type)
        if not md_doc:
            raise HTTPException(status_code=404, detail="Entity file not found")
        
        metadata = md_doc.get("metadata", {})
        content = md_doc.get("content", "")
        
        # Get relationships from graph
        relationships = graph_store.get_relationships(entity_id)
        
        return {
            "id": entity_id,
            "type": entity_type,
            "metadata": metadata,
            "content": content,
            "relationships": relationships,
            "custom_fields": metadata.get("custom_fields", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/entities/{entity_id}")
async def update_entity(entity_id: str, updates: UpdateEntityRequest):
    """
    Update an entity's editable properties.
    
    Protected fields (cannot be changed):
    - id, entity_type, created_at, source
    
    Auto-updated:
    - updated_at (set to current time)
    """
    try:
        # Get existing entity
        entity = registry.get(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_type = entity.get("type")
        
        # Read full markdown file
        md_doc = md_store.read_by_id(entity_id, entity_type)
        if not md_doc:
            raise HTTPException(status_code=404, detail="Entity file not found")
        
        metadata = md_doc.get("metadata", {})
        content = md_doc.get("content", "")
        
        # Build updates dict (excluding None values)
        update_dict = updates.model_dump(exclude_none=True)
        
        # Protected fields - remove if present
        protected_fields = {"id", "entity_type", "created_at", "source", "type"}
        for field in protected_fields:
            update_dict.pop(field, None)
        
        # Handle custom_fields merge
        if "custom_fields" in update_dict:
            existing_custom = metadata.get("custom_fields", {})
            # Merge - new values override, None removes
            for key, value in update_dict["custom_fields"].items():
                if value is None:
                    existing_custom.pop(key, None)
                else:
                    existing_custom[key] = value
            update_dict["custom_fields"] = existing_custom
        
        # Apply updates to metadata
        for key, value in update_dict.items():
            metadata[key] = value
        
        # Auto-update timestamp
        metadata["updated_at"] = datetime.now().isoformat()
        
        # Update content title if name/title changed
        if entity_type == "person" and "name" in update_dict:
            # Update title line in content
            lines = content.split("\n")
            if lines and lines[0].startswith("#"):
                lines[0] = f"# {update_dict['name']}"
                content = "\n".join(lines)
        elif "title" in update_dict and entity_type in ["goal", "event"]:
            lines = content.split("\n")
            if lines and lines[0].startswith("#"):
                lines[0] = f"# {update_dict['title']}"
                content = "\n".join(lines)
        elif entity_type in ["project", "period"] and "name" in update_dict:
            lines = content.split("\n")
            if lines and lines[0].startswith("#"):
                lines[0] = f"# {update_dict['name']}"
                content = "\n".join(lines)
        
        # Write back to markdown file
        import frontmatter
        post = frontmatter.Post(content, **metadata)
        filepath = md_doc.get("path")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        # Re-index in registry
        registry.index(
            doc_id=entity_id,
            path=str(filepath),
            entity_type=entity_type,
            name=metadata.get("name") or metadata.get("title"),
            checksum=md_store._compute_checksum(frontmatter.dumps(post)),
            content=content,
        )
        
        # Update in Neo4j
        graph_store.update_node(entity_id, update_dict)
        
        logger.info(f"Updated entity {entity_id}")
        
        return {
            "success": True,
            "message": f"Updated {entity_type} successfully",
            "entity_id": entity_id,
            "updated_fields": list(update_dict.keys()),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/entities/{entity_id}")
async def delete_entity(entity_id: str, hard_delete: bool = False):
    """
    Delete an entity.
    
    Args:
        entity_id: The entity ID to delete
        hard_delete: If True, permanently delete. If False (default), soft delete.
    
    Deletes:
    - The entity's markdown file
    - The entity from the registry (SQLite)
    - The entity from the graph store (Neo4j)
    - Associated documents (General Info, etc.)
    """
    try:
        # Get existing entity
        entity = registry.get(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_type = entity.get("type")
        entity_name = entity.get("name") or entity.get("title", "Unknown")
        
        # Get the markdown file path
        md_doc = md_store.read_by_id(entity_id, entity_type)
        filepath = md_doc.get("path") if md_doc else None
        
        # Delete associated documents (General Info, etc.)
        docs = registry.list_entity_documents(entity_id)
        for doc in docs:
            try:
                doc_md = md_store.read_document(doc["id"])
                if doc_md and doc_md.get("path"):
                    import os
                    os.remove(doc_md["path"])
                registry.delete(doc["id"])
                logger.info(f"Deleted associated document {doc['id']}")
            except Exception as doc_err:
                logger.warning(f"Failed to delete document {doc.get('id')}: {doc_err}")
        
        # Delete from graph store
        try:
            graph_store.delete_node(entity_id)
            logger.info(f"Deleted entity from graph: {entity_id}")
        except Exception as graph_err:
            logger.warning(f"Failed to delete from graph: {graph_err}")
        
        # Delete from registry
        registry.delete(entity_id)
        logger.info(f"Deleted entity from registry: {entity_id}")
        
        # Delete markdown file
        if filepath:
            import os
            try:
                os.remove(filepath)
                logger.info(f"Deleted markdown file: {filepath}")
            except Exception as file_err:
                logger.warning(f"Failed to delete file {filepath}: {file_err}")
        
        logger.info(f"Deleted {entity_type}: {entity_name} ({entity_id})")
        
        return {
            "success": True,
            "message": f"Deleted {entity_type} '{entity_name}' successfully",
            "entity_id": entity_id,
            "entity_type": entity_type,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Period Endpoints
# ==========================================

@app.get("/periods")
async def list_periods():
    """List all periods."""
    docs = registry.list_by_type(EntityType.PERIOD)
    return {"periods": docs, "count": len(docs)}


@app.get("/periods/incomplete")
async def list_incomplete_periods():
    """List periods that are missing start_date or end_date."""
    docs = registry.list_by_type(EntityType.PERIOD)
    
    incomplete = []
    for doc in docs:
        # Read full document to check dates
        md_doc = md_store.read_by_id(doc.get("id"), EntityType.PERIOD)
        if md_doc:
            metadata = md_doc.get("metadata", {})
            start_date = metadata.get("start_date")
            end_date = metadata.get("end_date")
            
            if not start_date or not end_date:
                incomplete.append({
                    **doc,
                    "has_start_date": bool(start_date),
                    "has_end_date": bool(end_date),
                })
    
    return {"periods": incomplete, "count": len(incomplete)}


@app.get("/periods/{period_id}")
async def get_period(period_id: str):
    """Get details for a specific period."""
    doc = registry.get(period_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Period not found")
    
    # Get full content from markdown
    md_doc = md_store.read_by_id(period_id, EntityType.PERIOD)
    content = md_doc.get("content", "") if md_doc else ""
    metadata = md_doc.get("metadata", {}) if md_doc else {}
    
    # Get relationships
    relationships = graph_store.get_relationships(period_id)
    
    # Determine completeness
    is_complete = bool(metadata.get("start_date") and metadata.get("end_date"))
    
    return {
        "id": period_id,
        "metadata": {
            **doc,
            **metadata,
        },
        "content": content,
        "relationships": relationships,
        "is_complete": is_complete,
    }


# ==========================================
# Document Endpoints
# ==========================================

@app.get("/documents")
async def list_documents():
    """List all documents in the system."""
    try:
        docs = registry.list_all_documents()
        return {"documents": docs, "count": len(docs)}
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return {"documents": [], "count": 0, "error": str(e)}


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get a document by ID."""
    # Try registry first
    doc = registry.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get full content from markdown
    md_doc = md_store.read_document(doc_id)
    content = md_doc.get("content", "") if md_doc else ""
    
    return {
        "id": doc_id,
        "metadata": doc,
        "content": content,
        "locked": doc.get("locked", 0) == 1,
    }


@app.post("/documents")
async def create_document(request: CreateDocumentRequest):
    """Create a new document."""
    from uuid import uuid4
    
    try:
        # Create the Document entity
        doc = Document(
            id=uuid4(),
            title=request.title,
            content=request.content,
            document_type=DocumentType(request.document_type),
            parent_entity_id=UUID(request.parent_entity_id) if request.parent_entity_id else None,
            parent_entity_type=EntityType(request.parent_entity_type) if request.parent_entity_type else None,
            source=Source.USER,
            locked=False,
        )
        
        # Write to markdown
        filepath = md_store.write_document(doc)
        
        # Index in registry
        # Note: Due to pydantic Config use_enum_values=True, enums are already strings
        registry.index(
            doc_id=str(doc.id),
            path=filepath,
            entity_type=EntityType.DOCUMENT,
            name=doc.title,
            checksum=md_store._compute_checksum(doc.content),
            content=doc.content,
            document_type=doc.document_type,  # Already a string
            parent_entity_id=str(doc.parent_entity_id) if doc.parent_entity_id else None,
            parent_entity_type=doc.parent_entity_type,  # Already a string or None
            locked=doc.locked,
        )
        
        return {
            "success": True,
            "document": {
                "id": str(doc.id),
                "title": doc.title,
                "document_type": doc.document_type,  # Already a string
                "path": str(filepath),
            }
        }
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")


@app.put("/documents/{doc_id}")
async def update_document(doc_id: str, request: UpdateDocumentRequest):
    """Update a document's title and/or content."""
    # Check if document exists and is not locked
    doc = registry.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.get("locked", 0) == 1:
        raise HTTPException(status_code=403, detail="Cannot edit locked document (General Info)")
    
    try:
        success = md_store.update_document(
            doc_id=doc_id,
            content=request.content,
            title=request.title,
            source=Source.USER,
        )
        
        if success:
            # Re-index
            md_doc = md_store.read_document(doc_id)
            if md_doc:
                registry.index(
                    doc_id=doc_id,
                    path=md_doc["path"],
                    entity_type=doc.get("type", "document"),
                    name=request.title or doc.get("name"),
                    checksum=md_doc["checksum"],
                    content=md_doc["content"],
                    document_type=doc.get("document_type"),
                    parent_entity_id=doc.get("parent_entity_id"),
                    parent_entity_type=doc.get("parent_entity_type"),
                    locked=doc.get("locked", 0) == 1,
                )
            
            return {"success": True, "message": "Document updated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update document")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update document: {str(e)}")


@app.post("/documents/{doc_id}/append")
async def append_to_document(doc_id: str, request: AppendDocumentRequest):
    """Append content to a document (for LLM use)."""
    doc = registry.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        success = md_store.append_to_document(
            doc_id=doc_id,
            content=request.content,
            source=Source.AGENT,  # API appends are from agent
            section=request.section,
        )
        
        if success:
            # Re-index
            md_doc = md_store.read_document(doc_id)
            if md_doc:
                registry.index(
                    doc_id=doc_id,
                    path=md_doc["path"],
                    entity_type=doc.get("type", "document"),
                    name=doc.get("name"),
                    checksum=md_doc["checksum"],
                    content=md_doc["content"],
                    document_type=doc.get("document_type"),
                    parent_entity_id=doc.get("parent_entity_id"),
                    parent_entity_type=doc.get("parent_entity_type"),
                    locked=doc.get("locked", 0) == 1,
                )
            
            return {"success": True, "message": "Content appended"}
        else:
            raise HTTPException(status_code=500, detail="Failed to append to document")
            
    except Exception as e:
        logger.error(f"Error appending to document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to append: {str(e)}")


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, hard: bool = False):
    """Delete a document (soft delete by default)."""
    doc = registry.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.get("locked", 0) == 1:
        raise HTTPException(status_code=403, detail="Cannot delete locked document (General Info)")
    
    try:
        # Get the file path
        md_doc = md_store.read_document(doc_id)
        if md_doc and md_doc.get("path"):
            md_store.delete(md_doc["path"], soft=not hard)
        
        # Remove from registry
        registry.delete(doc_id)
        
        # Log audit
        registry.log_audit(doc_id, "delete" if hard else "soft_delete")
        
        return {"success": True, "message": "Document deleted"}
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@app.get("/entities/{entity_id}/documents")
async def list_entity_documents(entity_id: str):
    """List all documents attached to an entity."""
    try:
        docs = registry.list_entity_documents(entity_id)
        
        # Also get from markdown for full content
        md_docs = md_store.list_entity_documents(entity_id)
        
        # Merge data - registry for metadata, markdown for content
        result = []
        for doc in docs:
            md_doc = next(
                (m for m in md_docs if m["metadata"].get("id") == doc["id"]), 
                None
            )
            result.append({
                **doc,
                "content": md_doc["content"] if md_doc else "",
            })
        
        return {"documents": result, "count": len(result)}
        
    except Exception as e:
        logger.error(f"Error listing entity documents: {e}")
        return {"documents": [], "count": 0, "error": str(e)}


@app.get("/entities/{entity_id}/general-info")
async def get_entity_general_info(entity_id: str):
    """Get the General Info document for an entity."""
    try:
        doc = registry.get_general_info_document(entity_id)
        if not doc:
            return {"exists": False, "document": None}
        
        # Get full content
        md_doc = md_store.read_document(doc["id"])
        content = md_doc.get("content", "") if md_doc else ""
        
        return {
            "exists": True,
            "document": {
                **doc,
                "content": content,
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting general info: {e}")
        return {"exists": False, "document": None, "error": str(e)}


# ==========================================
# Chat/Query Endpoints (Using CrewAI)
# ==========================================

@app.post("/chat")
async def chat(message: ChatMessage):
    """Send a message to the agent (uses CrewAI query agent)."""
    try:
        crew = get_crew_instance()
        result = crew.query(message.message)
        
        return {
            "success": result.success,
            "answer": result.answer,
            "sources": result.sources,
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "success": False,
            "answer": f"Error: {str(e)}",
            "sources": [],
        }


@app.post("/add")
async def add_note(request: AddNoteRequest):
    """Add new content to the knowledge graph (uses CrewAI ingestion agent)."""
    try:
        crew = get_crew_instance()
        result = crew.ingest(request.content)
        
        return {
            "success": result.success,
            "message": result.message,
            "entities": result.entities,
            "relationships": result.relationships,
            "needs_confirmation": result.needs_confirmation,
        }
    except Exception as e:
        logger.error(f"Add error: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "entities": [],
            "relationships": [],
        }


# ==========================================
# Timeline Endpoint
# ==========================================

@app.get("/timeline")
async def get_timeline(days: int = 7):
    """Get timeline of recent events."""
    since = datetime.now() - timedelta(days=days)
    
    events = registry.list_by_type(EntityType.EVENT)
    notes = registry.list_by_type(EntityType.NOTE)
    
    timeline = []
    for item in events + notes:
        created = item.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if dt >= since:
                    timeline.append({
                        "id": item.get("id"),
                        "date": created,
                        "name": item.get("name") or item.get("title", "Unknown"),
                        "type": item.get("type"),
                    })
            except:
                pass
    
    # Sort by date descending
    timeline.sort(key=lambda x: x["date"], reverse=True)
    
    return {"timeline": timeline, "count": len(timeline)}


# ==========================================
# Conversation Management Endpoints
# ==========================================

@app.get("/conversations")
async def list_conversations(limit: int = 50):
    """List all conversations with preview."""
    try:
        conversations = conv_store.list_conversations_with_preview(limit=limit)
        return {"conversations": conversations, "count": len(conversations)}
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return {"conversations": [], "count": 0, "error": str(e)}


@app.post("/conversations")
async def create_new_conversation(name: str | None = None):
    """Create a new conversation."""
    try:
        conv_id = conv_store.create_conversation(name=name)
        return {
            "success": True,
            "conversation_id": conv_id,
            "name": name or "New Chat",
        }
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conv_id}")
async def get_conversation_detail(conv_id: str, include_messages: bool = True):
    """Get a conversation with its messages."""
    try:
        conv = conv_store.get_conversation_summary(conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        result = {
            "conversation": conv,
        }
        
        if include_messages:
            messages = conv_store.get_messages(conv_id, limit=100)
            result["messages"] = messages
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/conversations/{conv_id}")
async def update_conversation(conv_id: str, request: UpdateConversationRequest):
    """Update a conversation's name."""
    try:
        success = conv_store.update_conversation(conv_id, name=request.name)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True, "message": "Conversation updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: str):
    """Delete a conversation and all its messages."""
    try:
        success = conv_store.delete_conversation(conv_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True, "message": "Conversation deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Conversational Interface (Proposal-based)
# ==========================================

# In-memory proposal storage (should be persisted in production)
_pending_proposals: dict[str, Any] = {}

@app.post("/conversation")
async def conversation(request: ConversationRequest):
    """
    Unified conversational endpoint that generates PROPOSALS for user review.
    
    Flow:
    1. Parse user input
    2. Extract entity mentions
    3. Find existing entity candidates
    4. Generate proposals (entities, relationships, documents)
    5. Return proposals for user review - NOTHING is created yet
    
    User must call /conversation/confirm to execute approved proposals.
    """
    from soml.mcp.proposals import ProposalGenerator, proposal_set_to_dict
    
    try:
        crew = get_crew_instance()
        
        # Ensure we have a conversation ID
        conversation_id = request.conversation_id or str(uuid4())
        
        # Check if conversation exists, create if not
        existing_conv = conv_store.get_conversation(conversation_id)
        if not existing_conv:
            conv_store.create_conversation(conversation_id)
        
        # Add user message
        conv_store.add_message(conversation_id, "user", request.message)
        
        # Step 1: Use CrewAI to parse and extract entities/relationships
        # But we WON'T execute them - just get the parsed data
        result = await crew.parse_only(
            text=request.message,
            conversation_id=conversation_id,
        )
        
        response = {
            "conversation_id": conversation_id,
        }
        
        # Step 2: If this is a question, answer it directly
        if result.get("intent", {}).get("type") == "query":
            query_result = crew.query(request.message, conversation_id)
            response["answer"] = query_result.answer if query_result.answer else "I don't have enough information to answer that."
            response["sources"] = query_result.sources
            response["requires_confirmation"] = False
            
            # Add assistant response to conversation
            conv_store.add_message(conversation_id, "assistant", response["answer"])
            return response
        
        # Step 3: Generate proposals from parsed entities/relationships
        parsed_entities = result.get("entities", [])
        parsed_relationships = result.get("relationships", [])
        
        if not parsed_entities and not parsed_relationships:
            # No entities found, treat as general chat
            response["answer"] = result.get("message", "I didn't find any specific information to add. Could you provide more details?")
            response["requires_confirmation"] = False
            return response
        
        # Generate proposals
        document_updates = result.get("document_updates", [])
        generator = ProposalGenerator()
        proposal_set = generator.generate_proposals(
            parsed_entities=parsed_entities,
            parsed_relationships=parsed_relationships,
            user_input=request.message,
            conversation_id=conversation_id,
            document_updates=document_updates,
        )
        
        # Store proposals for later confirmation
        _pending_proposals[proposal_set.proposal_set_id] = proposal_set
        
        # Build response with proposals
        response["requires_confirmation"] = True
        response["proposal_set"] = proposal_set_to_dict(proposal_set)
        response["message"] = _build_proposal_message(proposal_set)
        
        return response
        
    except Exception as e:
        logger.error(f"Conversation error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "conversation_id": request.conversation_id,
            "requires_confirmation": False,
            "answer": f"Error processing request: {str(e)}",
            "error": str(e),
        }


def _build_proposal_message(proposal_set) -> str:
    """Build a human-readable summary of proposals."""
    parts = []
    
    if proposal_set.entity_proposals:
        entity_summary = []
        for p in proposal_set.entity_proposals:
            existing_count = len([c for c in p.candidates if not c.is_create_new])
            
            # Build date info string
            date_info = ""
            if p.inferred_type == "period":
                if p.start_date or p.end_date:
                    start = p.start_date or "?"
                    end = p.end_date or "ongoing"
                    date_info = f" [From {start} to {end}]"
            elif p.inferred_type == "event" and p.on_date:
                date_info = f" [On {p.on_date}]"
            
            if existing_count > 0:
                entity_summary.append(f"**{p.mention}** ({p.inferred_type}){date_info} - found {existing_count} possible matches")
            else:
                entity_summary.append(f"**{p.mention}** ({p.inferred_type}){date_info} - will create new")
        parts.append("Entities:\n" + "\n".join(f"• {s}" for s in entity_summary))
    
    if proposal_set.relationship_proposals:
        rel_summary = []
        for p in proposal_set.relationship_proposals:
            action_word = "Add" if p.action == "add" else f"Change from {p.old_type} to"
            rel_summary.append(f"{action_word} **{p.relationship_type}** between {p.source_mention} and {p.target_mention}")
        parts.append("Relationships:\n" + "\n".join(f"• {s}" for s in rel_summary))
    
    return "\n\n".join(parts) if parts else "No changes to propose."


@app.post("/conversation/confirm")
async def confirm_proposal(request: ProposalConfirmRequest):
    """
    Execute user-approved proposals.
    
    This endpoint executes ONLY the proposals that the user has approved.
    Entity selections determine which existing entity to link or whether to create new.
    Relationship approvals determine which relationships to create.
    """
    from soml.mcp.proposals import execute_approved_proposals
    
    conv_id = request.conversation_id
    proposal_set_id = request.proposal_set_id
    
    # Verify conversation exists
    if not conv_store.get_conversation(conv_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get the pending proposal set
    proposal_set = _pending_proposals.get(proposal_set_id)
    if not proposal_set:
        raise HTTPException(status_code=404, detail="Proposal set not found or expired")
    
    try:
        # Execute approved proposals
        result = execute_approved_proposals(
            proposal_set=proposal_set,
            user_selections={
                "entity_selections": request.entity_selections,
                "entity_descriptions": request.entity_descriptions,
                "relationship_approvals": request.relationship_approvals,
                "document_approvals": request.document_approvals,
            },
        )
        
        # Clean up pending proposal
        del _pending_proposals[proposal_set_id]
        
        # Build response
        created_count = len(result.get("entities_created", []))
        linked_count = len(result.get("entities_linked", []))
        rel_count = len(result.get("relationships_created", []))
        doc_count = len(result.get("documents_created", []))
        errors = result.get("errors", [])
        
        msg_parts = []
        if created_count:
            msg_parts.append(f"{created_count} new entities created")
        if linked_count:
            msg_parts.append(f"{linked_count} linked to existing")
        if rel_count:
            msg_parts.append(f"{rel_count} relationships created")
        if doc_count:
            msg_parts.append(f"{doc_count} documents updated")
        if errors:
            msg_parts.append(f"{len(errors)} errors")
        
        # Add confirmation message to conversation
        msg = f"✅ Saved {', '.join(msg_parts)} to your knowledge graph!" if msg_parts else "No changes needed."
        conv_store.add_message(conv_id, "assistant", msg)
        
        return {
            "success": True,
            "message": msg,
            "created_entities": result.get("entities_created", []),
            "linked_entities": result.get("entities_linked", []),
            "relationships": result.get("relationships_created", []),
            "documents": result.get("documents_created", []),
            "errors": errors,
        }
            
    except Exception as e:
        logger.error(f"Confirm error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error saving: {str(e)}",
        }


# ==========================================
# Open Loops Endpoint (MCP Tools)
# ==========================================

@app.get("/open-loops")
async def get_open_loops():
    """Get open loops for attention using MCP tools."""
    try:
        from soml.mcp import tools as mcp_tools
        
        loops = mcp_tools.detect_open_loops()
        return {
            "loops": loops,
            "count": len(loops),
        }
    except Exception as e:
        logger.error(f"Open loops error: {e}")
        return {"loops": [], "count": 0, "error": str(e)}


# ==========================================
# Run with uvicorn
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

