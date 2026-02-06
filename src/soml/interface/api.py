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
from soml.storage.audit import AuditLog

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
audit = AuditLog(registry)


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
    
    # Build a map of relationship counts per entity from Neo4j
    rel_counts = {}
    try:
        with graph_store.session() as session:
            count_result = session.run("""
                MATCH (e:Entity)-[r:RELATES_TO]-(other:Entity)
                RETURN e.id AS id, count(DISTINCT other) AS total_rels
            """)
            for record in count_result:
                rel_counts[record["id"]] = record["total_rels"]
    except Exception:
        pass
    
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
            eid = doc.get("id")
            nodes.append({
                "id": eid,
                "label": doc.get("name") or doc.get("title", "Unknown"),
                "type": doc.get("type"),
                "group": doc.get("type"),
                "total_relationships": rel_counts.get(eid, 0),
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


@app.get("/graph/ego/{node_id}")
async def get_ego_graph(node_id: str, depth: int = 1):
    """Get ego-graph: a subgraph centered on node_id with `depth` hops.
    
    Returns nodes within N hops, edges between them, and for each node
    its total_relationships count so the UI can show hidden-connection indicators.
    """
    if depth < 1:
        depth = 1
    if depth > 5:
        depth = 5
    
    nodes = []
    edges = []
    node_ids = set()
    
    try:
        with graph_store.session() as session:
            # Get all nodes within N hops of the center node
            result = session.run("""
                MATCH path = (center:Entity {id: $center_id})-[:RELATES_TO*1..%d]-(neighbor:Entity)
                WITH collect(DISTINCT neighbor) + collect(DISTINCT center) AS all_nodes
                UNWIND all_nodes AS n
                WITH DISTINCT n
                OPTIONAL MATCH (n)-[r:RELATES_TO]-(other:Entity)
                WITH n, count(DISTINCT other) AS total_rels
                RETURN n.id AS id, n.name AS name, labels(n) AS labels, total_rels
            """ % depth, center_id=node_id)
            
            for record in result:
                nid = record["id"]
                if nid and nid not in node_ids:
                    node_ids.add(nid)
                    # Determine entity type from labels
                    labels = record["labels"] or []
                    entity_type = "note"
                    for lbl in labels:
                        low = lbl.lower()
                        if low in ("person", "project", "goal", "event", "period"):
                            entity_type = low
                            break
                    nodes.append({
                        "id": nid,
                        "label": record["name"] or "Unknown",
                        "type": entity_type,
                        "group": entity_type,
                        "total_relationships": record["total_rels"] or 0,
                    })
            
            # If center node wasn't found via paths (it has no relationships), add it directly
            if node_id not in node_ids:
                center_result = session.run("""
                    MATCH (n:Entity {id: $id})
                    OPTIONAL MATCH (n)-[r:RELATES_TO]-(other:Entity)
                    WITH n, count(DISTINCT other) AS total_rels
                    RETURN n.id AS id, n.name AS name, labels(n) AS labels, total_rels
                """, id=node_id)
                rec = center_result.single()
                if rec:
                    labels = rec["labels"] or []
                    entity_type = "note"
                    for lbl in labels:
                        low = lbl.lower()
                        if low in ("person", "project", "goal", "event", "period"):
                            entity_type = low
                            break
                    nodes.append({
                        "id": rec["id"],
                        "label": rec["name"] or "Unknown",
                        "type": entity_type,
                        "group": entity_type,
                        "total_relationships": rec["total_rels"] or 0,
                    })
                    node_ids.add(node_id)
                else:
                    # Node not in graph, try registry
                    registry_doc = registry.get(node_id)
                    if registry_doc:
                        nodes.append({
                            "id": node_id,
                            "label": registry_doc.get("name") or registry_doc.get("title", "Unknown"),
                            "type": registry_doc.get("type", "note"),
                            "group": registry_doc.get("type", "note"),
                            "total_relationships": 0,
                        })
                        node_ids.add(node_id)
            
            # Get edges between visible nodes only
            if node_ids:
                edge_result = session.run("""
                    MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
                    WHERE a.id IN $ids AND b.id IN $ids
                    RETURN a.id AS source, b.id AS target, r.type AS type
                """, ids=list(node_ids))
                for record in edge_result:
                    edges.append({
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"] or "related",
                    })
    except Exception as e:
        print(f"Error fetching ego graph: {e}")
        # Fallback: try to get at least the center node from registry
        registry_doc = registry.get(node_id)
        if registry_doc:
            nodes.append({
                "id": node_id,
                "label": registry_doc.get("name") or registry_doc.get("title", "Unknown"),
                "type": registry_doc.get("type", "note"),
                "group": registry_doc.get("type", "note"),
                "total_relationships": 0,
            })
    
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

def _get_relationship_counts() -> dict[str, int]:
    """Get relationship counts per entity from Neo4j."""
    rel_counts: dict[str, int] = {}
    try:
        with graph_store.session() as session:
            result = session.run("""
                MATCH (e:Entity)-[r:RELATES_TO]-(other:Entity)
                RETURN e.id AS id, count(DISTINCT other) AS total_rels
            """)
            for record in result:
                rel_counts[record["id"]] = record["total_rels"]
    except Exception:
        pass
    return rel_counts


def _enrich_entities(docs: list[dict]) -> list[dict]:
    """Enrich entity docs with relationship counts."""
    rel_counts = _get_relationship_counts()
    for doc in docs:
        doc["total_relationships"] = rel_counts.get(doc.get("id", ""), 0)
    return docs


@app.get("/entities/{entity_type}")
async def list_entities(entity_type: str):
    """List all entities of a given type."""
    try:
        docs = registry.list_by_type(entity_type)
        return {"entities": _enrich_entities(docs), "count": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/people")
async def list_people():
    """List all people."""
    docs = registry.list_by_type(EntityType.PERSON)
    return {"people": _enrich_entities(docs), "count": len(docs)}


@app.get("/projects")
async def list_projects():
    """List all projects."""
    docs = registry.list_by_type(EntityType.PROJECT)
    return {"projects": _enrich_entities(docs), "count": len(docs)}


@app.get("/goals")
async def list_goals():
    """List all goals."""
    docs = registry.list_by_type(EntityType.GOAL)
    return {"goals": _enrich_entities(docs), "count": len(docs)}


@app.get("/events")
async def list_events():
    """List all events."""
    docs = registry.list_by_type(EntityType.EVENT)
    return {"events": _enrich_entities(docs), "count": len(docs)}


@app.get("/notes")
async def list_notes():
    """List all notes."""
    docs = registry.list_by_type(EntityType.NOTE)
    return {"notes": _enrich_entities(docs), "count": len(docs)}


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
        
        # Audit log: capture before/after state
        entity_name = metadata.get("name") or metadata.get("title", "Unknown")
        audit.log_update(
            document_id=entity_id,
            old_data={"metadata": {k: md_doc.get("metadata", {}).get(k) for k in update_dict.keys()}},
            new_data={"metadata": update_dict},
            actor="user",
            item_type="entity",
            item_name=entity_name,
        )
        
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
    
    Soft delete:
    - Markdown files moved to .deleted/ folder (recoverable)
    - Registry and graph entries removed
    - Full state captured in audit log for undo
    
    Hard delete:
    - Permanent removal from all stores
    """
    try:
        # Get existing entity
        entity = registry.get(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_type = entity.get("type")
        entity_name = entity.get("name") or entity.get("title", "Unknown")
        
        # Capture full entity state for audit log (enables undo)
        md_doc = md_store.read_by_id(entity_id, entity_type)
        filepath = md_doc.get("path") if md_doc else None
        
        entity_snapshot = {
            "registry": entity,
            "metadata": md_doc.get("metadata", {}) if md_doc else {},
            "content": md_doc.get("content", "") if md_doc else "",
            "filepath": str(filepath) if filepath else None,
        }
        
        # Delete associated documents (General Info, etc.)
        docs = registry.list_entity_documents(entity_id)
        doc_snapshots = []
        for doc in docs:
            try:
                doc_md = md_store.read_document(doc["id"])
                doc_snapshot = {
                    "registry": doc,
                    "content": doc_md.get("content", "") if doc_md else "",
                    "metadata": doc_md.get("metadata", {}) if doc_md else {},
                    "filepath": str(doc_md.get("path", "")) if doc_md else "",
                }
                doc_snapshots.append(doc_snapshot)
                
                if doc_md and doc_md.get("path"):
                    from pathlib import Path as PathObj
                    md_store.delete(PathObj(doc_md["path"]), soft=not hard_delete)
                
                # Delete document from Neo4j graph
                try:
                    graph_store.delete_document_node(doc["id"])
                except Exception:
                    pass
                
                registry.delete(doc["id"])
                
                # Audit each document deletion
                audit.log_delete(
                    document_id=doc["id"],
                    data=doc_snapshot,
                    soft=not hard_delete,
                    actor="user",
                    item_type="document",
                    item_name=doc.get("name", "Document"),
                )
                
                logger.info(f"Deleted associated document {doc['id']}")
            except Exception as doc_err:
                logger.warning(f"Failed to delete document {doc.get('id')}: {doc_err}")
        
        # Delete from graph store (entity node + all relationships)
        try:
            graph_store.delete_node(entity_id)
            logger.info(f"Deleted entity from graph: {entity_id}")
        except Exception as graph_err:
            logger.warning(f"Failed to delete from graph: {graph_err}")
        
        # Delete from registry
        registry.delete(entity_id)
        logger.info(f"Deleted entity from registry: {entity_id}")
        
        # Delete/soft-delete markdown file
        if filepath:
            from pathlib import Path as PathObj
            try:
                md_store.delete(PathObj(filepath), soft=not hard_delete)
                logger.info(f"{'Soft' if not hard_delete else 'Hard'} deleted markdown file: {filepath}")
            except Exception as file_err:
                logger.warning(f"Failed to delete file {filepath}: {file_err}")
        
        # Audit log: capture full entity state for undo
        entity_snapshot["documents"] = doc_snapshots
        audit.log_delete(
            document_id=entity_id,
            data=entity_snapshot,
            soft=not hard_delete,
            actor="user",
            item_type="entity",
            item_name=entity_name,
        )
        
        logger.info(f"Deleted {entity_type}: {entity_name} ({entity_id})")
        
        return {
            "success": True,
            "message": f"Deleted {entity_type} '{entity_name}' successfully",
            "entity_id": entity_id,
            "entity_type": entity_type,
            "soft_delete": not hard_delete,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Relationship Endpoints
# ==========================================

class CreateRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    direction: str = "outgoing"  # outgoing, incoming, bidirectional
    properties: dict = {}
    allow_multiple: bool = False

class UpdateRelationshipRequest(BaseModel):
    type: str | None = None
    direction: str | None = None  # outgoing, incoming, bidirectional
    context: str | None = None
    notes: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


@app.get("/relationships/between")
async def get_relationships_between(source_id: str, target_id: str):
    """Get all relationships between two specific entities."""
    try:
        # Get all relationships from source
        source_rels = graph_store.get_relationships(source_id)
        
        # Filter to only those connecting to target (in either direction)
        between = []
        for rel in source_rels:
            if rel.get("other_id") == target_id:
                between.append({
                    **rel,
                    "source_id": source_id,
                    "target_id": target_id,
                    "direction": "outgoing",
                })
        
        # Also check reverse direction
        target_rels = graph_store.get_relationships(target_id)
        for rel in target_rels:
            if rel.get("other_id") == source_id:
                # Check if this is already counted (avoid duplicates)
                rel_id = rel.get("id")
                if rel_id and not any(r.get("id") == rel_id for r in between):
                    between.append({
                        **rel,
                        "source_id": target_id,
                        "target_id": source_id,
                        "direction": "incoming",  # from perspective of original source
                    })
        
        return {"relationships": between, "count": len(between)}
    except Exception as e:
        logger.error(f"Error getting relationships between entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/relationships/{relationship_id}")
async def get_relationship(relationship_id: str):
    """Get a specific relationship by ID."""
    try:
        with graph_store.session() as session:
            result = session.run("""
                MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                RETURN 
                    r.id as id,
                    r.type as type,
                    r.category as category,
                    r.direction as direction,
                    r.strength as strength,
                    r.sentiment as sentiment,
                    r.confidence as confidence,
                    r.context as context,
                    r.notes as notes,
                    r.started_at as started_at,
                    r.ended_at as ended_at,
                    r.created_at as created_at,
                    r.source as source,
                    source.id as source_id,
                    source.name as source_name,
                    target.id as target_id,
                    target.name as target_name
            """, rel_id=relationship_id)
            
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Relationship not found")
            
            data = dict(record)
            # Default direction to outgoing if not set
            if not data.get("direction"):
                data["direction"] = "outgoing"
            
            return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/relationships")
async def create_relationship(request: CreateRelationshipRequest):
    """Create a new relationship between entities."""
    from soml.mcp import tools as mcp_tools
    
    try:
        # Handle direction by swapping source/target for incoming
        actual_source = request.source_id
        actual_target = request.target_id
        
        if request.direction == "incoming":
            actual_source = request.target_id
            actual_target = request.source_id
        
        # Add direction to properties
        props = request.properties.copy()
        props["direction"] = request.direction
        
        result = mcp_tools.add_relationship(
            source_id=actual_source,
            target_id=actual_target,
            rel_type=request.relationship_type,
            properties=props,
            allow_multiple=request.allow_multiple,
        )
        
        # For bidirectional, create the reverse relationship too
        if request.direction == "bidirectional" and result.action == "created":
            reverse_props = props.copy()
            reverse_props["direction"] = "bidirectional"
            mcp_tools.add_relationship(
                source_id=request.target_id,
                target_id=request.source_id,
                rel_type=request.relationship_type,
                properties=reverse_props,
                allow_multiple=True,  # Allow since main relationship exists
            )
        
        if result.action == "created":
            # Audit log
            source_entity = registry.get(request.source_id)
            target_entity = registry.get(request.target_id)
            source_name = (source_entity.get("name") or source_entity.get("title", "Unknown")) if source_entity else "Unknown"
            target_name = (target_entity.get("name") or target_entity.get("title", "Unknown")) if target_entity else "Unknown"
            audit.log_create(
                document_id=result.relationship_id or "unknown",
                data={
                    "source_id": request.source_id,
                    "target_id": request.target_id,
                    "type": request.relationship_type,
                    "direction": request.direction,
                },
                actor="user",
                item_type="relationship",
                item_name=f"{source_name} → {target_name} ({request.relationship_type})",
            )
            
            return {
                "success": True,
                "action": "created",
                "relationship_id": result.relationship_id,
                "direction": request.direction,
            }
        elif result.action == "exists":
            return {
                "success": True,
                "action": "exists",
                "relationship_id": result.relationship_id,
                "message": "Relationship already exists",
            }
        else:
            raise HTTPException(status_code=500, detail=result.error or "Failed to create relationship")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/relationships/{relationship_id}")
async def update_relationship(relationship_id: str, request: UpdateRelationshipRequest):
    """Update a relationship's properties."""
    try:
        # Build update dict from non-None values
        updates = request.model_dump(exclude_none=True)
        
        if not updates:
            return {"success": True, "message": "No updates provided"}
        
        # Capture before-state
        old_data = {}
        with graph_store.session() as session:
            old_result = session.run("""
                MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                RETURN properties(r) as props, source.name as source_name, target.name as target_name
            """, rel_id=relationship_id)
            old_record = old_result.single()
            if old_record:
                old_data = dict(old_record["props"]) if old_record["props"] else {}
                source_name = old_record["source_name"] or "Unknown"
                target_name = old_record["target_name"] or "Unknown"
            else:
                source_name = "Unknown"
                target_name = "Unknown"
        
        # Add updated_at timestamp
        updates["updated_at"] = datetime.now().isoformat()
        
        with graph_store.session() as session:
            # Update the relationship
            result = session.run("""
                MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                SET r += $updates
                RETURN r.id as id, r.type as type
            """, rel_id=relationship_id, updates=updates)
            
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Relationship not found")
        
        # Audit log
        rel_type = updates.get("type") or old_data.get("type", "relationship")
        audit.log_update(
            document_id=relationship_id,
            old_data={k: old_data.get(k) for k in updates.keys() if k != "updated_at"},
            new_data=updates,
            actor="user",
            item_type="relationship",
            item_name=f"{source_name} → {target_name} ({rel_type})",
        )
        
        return {
            "success": True,
            "message": "Relationship updated",
            "relationship_id": relationship_id,
            "updated_fields": list(updates.keys()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/relationships/{relationship_id}")
async def delete_relationship_endpoint(relationship_id: str):
    """Delete a relationship by ID."""
    try:
        # Capture before-state for audit
        rel_snapshot = {}
        source_name = "Unknown"
        target_name = "Unknown"
        with graph_store.session() as session:
            old_result = session.run("""
                MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                RETURN properties(r) as props, source.id as source_id, source.name as source_name,
                       target.id as target_id, target.name as target_name
            """, rel_id=relationship_id)
            old_record = old_result.single()
            if old_record:
                rel_snapshot = {
                    "properties": dict(old_record["props"]) if old_record["props"] else {},
                    "source_id": old_record["source_id"],
                    "target_id": old_record["target_id"],
                }
                source_name = old_record["source_name"] or "Unknown"
                target_name = old_record["target_name"] or "Unknown"
        
        with graph_store.session() as session:
            # Delete the relationship
            result = session.run("""
                MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                DELETE r
                RETURN count(*) as deleted
            """, rel_id=relationship_id)
            
            record = result.single()
            if not record or record["deleted"] == 0:
                raise HTTPException(status_code=404, detail="Relationship not found")
        
        # Audit log
        rel_type = rel_snapshot.get("properties", {}).get("type", "relationship")
        audit.log_delete(
            document_id=relationship_id,
            data=rel_snapshot,
            soft=False,  # Neo4j relationships can't be soft-deleted
            actor="user",
            item_type="relationship",
            item_name=f"{source_name} → {target_name} ({rel_type})",
        )
        
        logger.info(f"Deleted relationship {relationship_id}")
        
        return {
            "success": True,
            "message": "Relationship deleted",
            "relationship_id": relationship_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting relationship: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/relationships/{relationship_id}/documents")
async def list_relationship_documents(relationship_id: str):
    """List all documents attached to a relationship."""
    try:
        docs = registry.list_relationship_documents(relationship_id)
        return {
            "documents": docs,
            "count": len(docs),
            "relationship_id": relationship_id,
        }
    except Exception as e:
        logger.error(f"Error listing relationship documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CreateRelationshipDocumentRequest(BaseModel):
    """Request body for creating a relationship document."""
    title: str
    content: str
    tags: list[str] | None = None
    document_type: str = "note"


@app.post("/relationships/{relationship_id}/documents")
async def create_relationship_document(relationship_id: str, request: CreateRelationshipDocumentRequest):
    """Create a document attached to a relationship."""
    from soml.mcp.tools.document import create_document
    
    try:
        result = create_document(
            title=request.title,
            content=request.content,
            parent_relationship_id=relationship_id,
            tags=request.tags,
            document_type=request.document_type,
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to create document"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating relationship document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Period Endpoints
# ==========================================

@app.get("/periods")
async def list_periods():
    """List all periods."""
    docs = registry.list_by_type(EntityType.PERIOD)
    return {"periods": _enrich_entities(docs), "count": len(docs)}


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
async def list_documents(
    entity_id: str | None = None,
    relationship_id: str | None = None,
    entity_type: str | None = None,
    tags: str | None = None,  # comma-separated
    search: str | None = None,
    limit: int = 100,
):
    """
    List documents with optional filters.
    
    - entity_id: Filter by parent entity
    - relationship_id: Filter by parent relationship
    - entity_type: Filter by parent entity type (person, project, etc.)
    - tags: Comma-separated list of tags to filter by (documents must have all tags)
    - search: Full-text search in document content
    - limit: Max number of results
    """
    try:
        # Start with all documents
        if search:
            docs = registry.search_documents(search, limit=limit)
        elif entity_id:
            docs = registry.list_entity_documents(entity_id)
        elif relationship_id:
            docs = registry.list_relationship_documents(relationship_id)
        else:
            docs = registry.list_all_documents()
        
        # Filter by entity_type if specified
        if entity_type:
            docs = [d for d in docs if d.get("parent_entity_type") == entity_type]
        
        # Filter by tags if specified
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if tag_list:
                # Get documents that have all specified tags
                tag_doc_ids = set()
                for tag_name in tag_list:
                    tag_items = graph_store.find_by_tag(tag_name)
                    tag_docs = {item["id"] for item in tag_items if item.get("type") == "Document"}
                    if not tag_doc_ids:
                        tag_doc_ids = tag_docs
                    else:
                        tag_doc_ids = tag_doc_ids.intersection(tag_docs)
                docs = [d for d in docs if d.get("id") in tag_doc_ids]
        
        # Apply limit
        docs = docs[:limit]
        
        return {"documents": docs, "count": len(docs)}
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return {"documents": [], "count": 0, "error": str(e)}


@app.get("/documents/summary")
async def get_documents_summary():
    """
    Get document counts grouped by entity type, entity, relationship, and tags.
    Used for building the document browser sidebar tree.
    """
    try:
        all_docs = registry.list_all_documents()
        
        # Group by entity type
        by_entity_type: dict[str, int] = {}
        by_entity: dict[str, dict] = {}
        by_relationship: dict[str, int] = {}
        orphan_count = 0
        
        for doc in all_docs:
            entity_type = doc.get("parent_entity_type")
            entity_id = doc.get("parent_entity_id")
            rel_id = doc.get("parent_relationship_id")
            
            if rel_id:
                by_relationship[rel_id] = by_relationship.get(rel_id, 0) + 1
            elif entity_id and entity_type:
                by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + 1
                if entity_id not in by_entity:
                    by_entity[entity_id] = {
                        "id": entity_id,
                        "type": entity_type,
                        "name": doc.get("name", "Unknown"),
                        "count": 0,
                    }
                by_entity[entity_id]["count"] += 1
            else:
                orphan_count += 1
        
        # Get entity names from registry
        for entity_id in by_entity:
            entity_doc = registry.get(entity_id)
            if entity_doc:
                by_entity[entity_id]["name"] = entity_doc.get("name", "Unknown")
        
        # Group by tags
        by_tag: dict[str, int] = {}
        all_tags = registry.get_all_tags()
        for tag in all_tags:
            tag_items = graph_store.find_by_tag(tag["name"])
            doc_count = sum(1 for item in tag_items if item.get("type") == "Document")
            if doc_count > 0:
                by_tag[tag["name"]] = doc_count
        
        # Get relationships with documents
        relationships_with_docs = []
        for rel_id, count in by_relationship.items():
            with graph_store.session() as session:
                result = session.run("""
                    MATCH (source:Entity)-[r:RELATES_TO {id: $rel_id}]->(target:Entity)
                    RETURN source.id as source_id, source.label as source_name,
                           target.id as target_id, target.label as target_name,
                           r.type as type
                """, rel_id=rel_id)
                record = result.single()
                if record:
                    relationships_with_docs.append({
                        "id": rel_id,
                        "source_id": record["source_id"],
                        "source_name": record["source_name"],
                        "target_id": record["target_id"],
                        "target_name": record["target_name"],
                        "type": record["type"],
                        "document_count": count,
                    })
        
        return {
            "total_count": len(all_docs),
            "by_entity_type": by_entity_type,
            "by_entity": list(by_entity.values()),
            "by_relationship": relationships_with_docs,
            "by_tag": by_tag,
            "orphan_count": orphan_count,
        }
    except Exception as e:
        logger.error(f"Error getting documents summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Audit log
        audit.log_create(
            document_id=str(doc.id),
            data={"title": doc.title, "document_type": doc.document_type, "content": doc.content[:500]},
            actor="user",
            item_type="document",
            item_name=doc.title,
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
        # Capture before-state for audit (full content snapshot)
        old_md_doc = md_store.read_document(doc_id)
        old_snapshot = {
            "title": doc.get("name"),
            "content": old_md_doc.get("content", "") if old_md_doc else "",
            "metadata": old_md_doc.get("metadata", {}) if old_md_doc else {},
        }
        
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
            
            # Audit log: capture before/after content for rollback
            new_snapshot = {
                "title": request.title or doc.get("name"),
                "content": md_doc.get("content", "") if md_doc else "",
            }
            audit.log_update(
                document_id=doc_id,
                old_data=old_snapshot,
                new_data=new_snapshot,
                actor="user",
                item_type="document",
                item_name=request.title or doc.get("name"),
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
        # Capture before-state for audit
        old_md_doc = md_store.read_document(doc_id)
        old_content = old_md_doc.get("content", "") if old_md_doc else ""
        
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
            
            # Audit log
            audit.log_update(
                document_id=doc_id,
                old_data={"content": old_content},
                new_data={"content": md_doc.get("content", "") if md_doc else "", "appended": request.content},
                actor="agent",
                item_type="document",
                item_name=doc.get("name"),
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
        # Capture full state for audit (enables undo/restore)
        md_doc = md_store.read_document(doc_id)
        doc_snapshot = {
            "registry": doc,
            "content": md_doc.get("content", "") if md_doc else "",
            "metadata": md_doc.get("metadata", {}) if md_doc else {},
            "filepath": str(md_doc.get("path", "")) if md_doc else "",
        }
        
        # Delete markdown file (soft or hard)
        if md_doc and md_doc.get("path"):
            from pathlib import Path as PathObj
            md_store.delete(PathObj(md_doc["path"]), soft=not hard)
        
        # Delete from Neo4j graph (removes vector embedding + edges)
        try:
            graph_store.delete_document_node(doc_id)
        except Exception as graph_err:
            logger.warning(f"Failed to delete document from graph: {graph_err}")
        
        # Remove from registry
        registry.delete(doc_id)
        
        # Audit log with full snapshot
        audit.log_delete(
            document_id=doc_id,
            data=doc_snapshot,
            soft=not hard,
            actor="user",
            item_type="document",
            item_name=doc.get("name", "Document"),
        )
        
        return {"success": True, "message": "Document deleted", "soft_delete": not hard}
        
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
# Folders
# ==========================================

class CreateFolderRequest(BaseModel):
    name: str
    parent_path: str = "/"
    entity_id: str | None = None


class MoveFolderRequest(BaseModel):
    new_parent_path: str


class RenameFolderRequest(BaseModel):
    new_name: str


@app.get("/folders")
async def get_folders(
    path: str = "/",
    entity_id: str | None = None,
    include_documents: bool = True,
):
    """Get folder tree starting from a path."""
    from soml.mcp.tools.folder import get_folder_tree
    try:
        return get_folder_tree(path, entity_id, include_documents)
    except Exception as e:
        logger.error(f"Get folders error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/folders/contents")
async def get_folder_contents_endpoint(
    path: str = "/",
    entity_id: str | None = None,
):
    """List documents and subfolders in a folder."""
    from soml.mcp.tools.folder import list_folder_contents
    try:
        return list_folder_contents(path, entity_id)
    except Exception as e:
        logger.error(f"Get folder contents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/folders")
async def create_folder_endpoint(request: CreateFolderRequest):
    """Create a new folder."""
    from soml.mcp.tools.folder import create_folder
    try:
        result = create_folder(request.name, request.parent_path, request.entity_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create folder"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/folders/{folder_path:path}/move")
async def move_folder_endpoint(folder_path: str, request: MoveFolderRequest):
    """Move a folder to a new location."""
    from soml.mcp.tools.folder import move_folder
    try:
        # Add leading slash if not present
        folder_path = f"/{folder_path}" if not folder_path.startswith("/") else folder_path
        result = move_folder(folder_path, request.new_parent_path)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to move folder"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Move folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/folders/{folder_path:path}/rename")
async def rename_folder_endpoint(folder_path: str, request: RenameFolderRequest):
    """Rename a folder."""
    from soml.mcp.tools.folder import rename_folder
    try:
        folder_path = f"/{folder_path}" if not folder_path.startswith("/") else folder_path
        result = rename_folder(folder_path, request.new_name)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to rename folder"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/folders/{folder_path:path}")
async def delete_folder_endpoint(folder_path: str, recursive: bool = False):
    """Delete a folder."""
    from soml.mcp.tools.folder import delete_folder
    try:
        folder_path = f"/{folder_path}" if not folder_path.startswith("/") else folder_path
        result = delete_folder(folder_path, recursive)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete folder"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/folders/{folder_path:path}/summary")
async def get_folder_summary_endpoint(folder_path: str, entity_id: str | None = None):
    """Get summary of folder contents for LLM context."""
    from soml.mcp.tools.organization import get_folder_summary
    try:
        folder_path = f"/{folder_path}" if not folder_path.startswith("/") else folder_path
        return get_folder_summary(folder_path, entity_id)
    except Exception as e:
        logger.error(f"Get folder summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Tags
# ==========================================

class CreateTagRequest(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class UpdateTagRequest(BaseModel):
    color: str | None = None
    description: str | None = None


class AddTagsRequest(BaseModel):
    tags: list[str]


@app.get("/tags")
async def get_tags():
    """Get all tags with usage counts."""
    from soml.mcp.tools.tag import get_all_tags
    try:
        return get_all_tags()
    except Exception as e:
        logger.error(f"Get tags error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tags")
async def create_tag_endpoint(request: CreateTagRequest):
    """Create a new tag."""
    from soml.mcp.tools.tag import create_tag
    try:
        result = create_tag(request.name, request.color, request.description)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create tag"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create tag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/tags/{tag_name}")
async def update_tag_endpoint(tag_name: str, request: UpdateTagRequest):
    """Update tag metadata."""
    from soml.mcp.tools.tag import update_tag
    try:
        result = update_tag(tag_name, request.color, request.description)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to update tag"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update tag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tags/{tag_name}")
async def delete_tag_endpoint(tag_name: str, force: bool = False):
    """Delete a tag."""
    from soml.mcp.tools.tag import delete_tag
    try:
        result = delete_tag(tag_name, force)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete tag"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete tag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tags/{tag_name}/items")
async def get_tag_items(
    tag_name: str,
    include_entities: bool = True,
    include_documents: bool = True,
):
    """Find all items with a specific tag."""
    from soml.mcp.tools.tag import find_by_tag
    try:
        return find_by_tag(tag_name, include_entities, include_documents)
    except Exception as e:
        logger.error(f"Find by tag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/entities/{entity_id}/tags")
async def add_entity_tags(entity_id: str, request: AddTagsRequest):
    """Add tags to an entity."""
    from soml.mcp.tools.tag import add_tags
    try:
        result = add_tags(entity_id, request.tags, item_type="entity")
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to add tags"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add entity tags error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/entities/{entity_id}/tags")
async def remove_entity_tags(entity_id: str, request: AddTagsRequest):
    """Remove tags from an entity."""
    from soml.mcp.tools.tag import remove_tags
    try:
        result = remove_tags(entity_id, request.tags, item_type="entity")
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove tags"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove entity tags error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/{doc_id}/tags")
async def add_document_tags(doc_id: str, request: AddTagsRequest):
    """Add tags to a document."""
    from soml.mcp.tools.tag import add_tags
    try:
        result = add_tags(doc_id, request.tags, item_type="document")
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to add tags"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add document tags error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{doc_id}/tags")
async def remove_document_tags(doc_id: str, request: AddTagsRequest):
    """Remove tags from a document."""
    from soml.mcp.tools.tag import remove_tags
    try:
        result = remove_tags(doc_id, request.tags, item_type="document")
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove tags"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove document tags error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/entities/{entity_id}/related")
async def get_related_items_endpoint(entity_id: str, include_self: bool = False):
    """Find items sharing tags with an entity."""
    from soml.mcp.tools.tag import get_related_items
    try:
        return get_related_items(entity_id, include_self)
    except Exception as e:
        logger.error(f"Get related items error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# User Entity
# ==========================================

class UpdateUserRequest(BaseModel):
    name: str | None = None
    tags: list[str] | None = None


class StoreUserNoteRequest(BaseModel):
    title: str
    content: str
    folder_path: str | None = None
    tags: list[str] | None = None


@app.get("/user")
async def get_user():
    """Get the user entity (creates if not exists)."""
    from soml.mcp.tools.user import get_or_create_user
    try:
        result = get_or_create_user()
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/user")
async def update_user_endpoint(request: UpdateUserRequest):
    """Update user entity information."""
    from soml.mcp.tools.user import update_user
    try:
        result = update_user(request.name, request.tags)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to update user"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/documents")
async def get_user_documents_endpoint(folder_path: str | None = None):
    """Get documents owned by the user entity."""
    from soml.mcp.tools.user import get_user_documents
    try:
        return get_user_documents(folder_path)
    except Exception as e:
        logger.error(f"Get user documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/user/notes")
async def store_user_note_endpoint(request: StoreUserNoteRequest):
    """Store a note under the user entity."""
    from soml.mcp.tools.user import store_user_note
    try:
        result = store_user_note(request.title, request.content, request.folder_path, request.tags)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to store note"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store user note error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Organization Intelligence
# ==========================================

class SuggestLocationRequest(BaseModel):
    content: str
    title: str | None = None
    entity_id: str | None = None


@app.get("/organization/issues")
async def get_organizational_issues(entity_id: str | None = None):
    """Find organizational problems that should be addressed."""
    from soml.mcp.tools.organization import find_organizational_issues
    try:
        return find_organizational_issues(entity_id)
    except Exception as e:
        logger.error(f"Get organizational issues error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/organization/suggest-location")
async def suggest_location_endpoint(request: SuggestLocationRequest):
    """Suggest folder and tags for document content."""
    from soml.mcp.tools.organization import suggest_document_location
    try:
        return suggest_document_location(request.content, request.title, request.entity_id)
    except Exception as e:
        logger.error(f"Suggest location error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/organization/suggest-reorganization")
async def suggest_reorganization_endpoint(folder_path: str, entity_id: str | None = None):
    """Analyze folder and suggest improvements."""
    from soml.mcp.tools.organization import suggest_reorganization
    try:
        return suggest_reorganization(folder_path, entity_id)
    except Exception as e:
        logger.error(f"Suggest reorganization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Activity & Audit Endpoints
# ==========================================

@app.get("/activity")
async def get_activity(
    limit: int = 50,
    item_type: str | None = None,
    actor: str | None = None,
    since: str | None = None,
):
    """
    Get recent activity across the entire system.
    
    Args:
        limit: Max entries to return (default 50)
        item_type: Filter by 'entity', 'document', or 'relationship'
        actor: Filter by 'user', 'agent', or 'system'
        since: ISO timestamp to filter from
    """
    try:
        entries = audit.get_recent_activity(
            limit=limit,
            item_type=item_type,
            actor=actor,
            since=since,
        )
        return {"activity": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"Error fetching activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/activity/entity/{entity_id}")
async def get_entity_activity(entity_id: str, limit: int = 50):
    """
    Get activity history for a specific entity and its documents.
    """
    try:
        entries = audit.get_entity_activity(entity_id, limit=limit)
        return {"activity": entries, "count": len(entries), "entity_id": entity_id}
    except Exception as e:
        logger.error(f"Error fetching entity activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/activity/item/{item_id}")
async def get_item_activity(item_id: str, limit: int = 50):
    """
    Get activity history for a specific item (entity, document, or relationship).
    """
    try:
        entries = audit.get_history(item_id, limit=limit)
        can_undo = audit.can_undo(item_id)
        return {
            "activity": entries,
            "count": len(entries),
            "item_id": item_id,
            "can_undo": can_undo,
        }
    except Exception as e:
        logger.error(f"Error fetching item activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/activity/undo/{item_id}")
async def undo_last_action(item_id: str):
    """
    Undo the last action on an item.
    
    Supports:
    - Undo document update: restores previous content
    - Undo document delete (soft): restores from .deleted/ + re-indexes
    - Undo entity update: restores previous metadata
    - Undo entity delete (soft): restores markdown + re-indexes
    - Undo relationship delete: re-creates the relationship
    """
    try:
        if not audit.can_undo(item_id):
            raise HTTPException(status_code=400, detail="No undoable action found for this item")
        
        history = audit.get_history(item_id, limit=1)
        if not history:
            raise HTTPException(status_code=404, detail="No history found")
        
        last_entry = history[0]
        action = last_entry["action"]
        old_data = last_entry.get("old_data", {})
        item_type = last_entry.get("item_type", "unknown")
        
        if action == "update" and item_type == "document":
            # Restore previous document content
            old_content = old_data.get("content") if isinstance(old_data, dict) else None
            old_title = old_data.get("title") if isinstance(old_data, dict) else None
            
            if old_content is not None:
                success = md_store.update_document(
                    doc_id=item_id,
                    content=old_content,
                    title=old_title,
                    source=Source.USER,
                )
                if success:
                    # Re-index
                    md_doc = md_store.read_document(item_id)
                    if md_doc:
                        doc_reg = registry.get(item_id)
                        registry.index(
                            doc_id=item_id,
                            path=md_doc["path"],
                            entity_type=doc_reg.get("type", "document") if doc_reg else "document",
                            name=old_title or (doc_reg.get("name") if doc_reg else "Document"),
                            checksum=md_doc["checksum"],
                            content=md_doc["content"],
                        )
                    
                    # Log the undo itself
                    audit.log(
                        document_id=item_id,
                        action="restore",
                        old_data=last_entry.get("new_data"),
                        new_data=old_data,
                        actor="user",
                        item_type=item_type,
                        item_name=old_title,
                    )
                    
                    return {"success": True, "message": "Document content restored", "action": "undo_update"}
            
            raise HTTPException(status_code=400, detail="No previous content to restore")
        
        elif action == "delete" and item_type == "document":
            # Restore soft-deleted document
            if isinstance(old_data, dict) and old_data.get("content"):
                filepath = old_data.get("filepath")
                reg_data = old_data.get("registry", {})
                metadata = old_data.get("metadata", {})
                
                # Try to restore from .deleted/ folder
                restored = False
                if filepath:
                    from pathlib import Path as PathObj
                    deleted_dir = md_store.data_dir / ".deleted"
                    if deleted_dir.exists():
                        for f in deleted_dir.iterdir():
                            if f.name.endswith(PathObj(filepath).name):
                                restored_path = md_store.restore(f)
                                if restored_path:
                                    restored = True
                                    # Re-index
                                    registry.index(
                                        doc_id=item_id,
                                        path=restored_path,
                                        entity_type=reg_data.get("type", "document"),
                                        name=reg_data.get("name", "Document"),
                                        checksum=md_store._compute_checksum(old_data["content"]),
                                        content=old_data["content"],
                                        document_type=reg_data.get("document_type"),
                                        parent_entity_id=reg_data.get("parent_entity_id"),
                                        parent_entity_type=reg_data.get("parent_entity_type"),
                                    )
                                    break
                
                if not restored:
                    # Recreate from snapshot
                    from uuid import UUID as UUIDType
                    doc = Document(
                        id=UUIDType(item_id),
                        title=reg_data.get("name", "Restored Document"),
                        document_type=DocumentType(reg_data.get("document_type", "note")),
                        content=old_data["content"],
                        parent_entity_id=UUIDType(reg_data["parent_entity_id"]) if reg_data.get("parent_entity_id") else None,
                        parent_entity_type=EntityType(reg_data["parent_entity_type"]) if reg_data.get("parent_entity_type") else None,
                        source=Source.USER,
                    )
                    filepath = md_store.write_document(doc)
                    registry.index(
                        doc_id=item_id,
                        path=filepath,
                        entity_type=EntityType.DOCUMENT,
                        name=doc.title,
                        checksum=md_store._compute_checksum(old_data["content"]),
                        content=old_data["content"],
                        document_type=reg_data.get("document_type"),
                        parent_entity_id=reg_data.get("parent_entity_id"),
                        parent_entity_type=reg_data.get("parent_entity_type"),
                    )
                
                audit.log(
                    document_id=item_id,
                    action="restore",
                    old_data=None,
                    new_data=old_data,
                    actor="user",
                    item_type="document",
                    item_name=reg_data.get("name", "Document"),
                )
                
                return {"success": True, "message": "Document restored", "action": "undo_delete"}
            
            raise HTTPException(status_code=400, detail="No snapshot data to restore document from")
        
        elif action == "update" and item_type == "entity":
            # Restore previous entity metadata
            if isinstance(old_data, dict) and old_data.get("metadata"):
                old_metadata = old_data["metadata"]
                
                # Read current entity
                md_doc = md_store.read_by_id(item_id, registry.get(item_id, {}).get("type") if registry.get(item_id) else None)
                if md_doc:
                    metadata = md_doc.get("metadata", {})
                    for key, value in old_metadata.items():
                        metadata[key] = value
                    metadata["updated_at"] = datetime.now().isoformat()
                    
                    import frontmatter
                    content = md_doc.get("content", "")
                    post = frontmatter.Post(content, **metadata)
                    filepath = md_doc.get("path")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(frontmatter.dumps(post))
                    
                    # Update graph
                    graph_store.update_node(item_id, old_metadata)
                    
                    # Re-index
                    entity = registry.get(item_id)
                    if entity:
                        registry.index(
                            doc_id=item_id,
                            path=str(filepath),
                            entity_type=entity.get("type"),
                            name=metadata.get("name") or metadata.get("title"),
                            checksum=md_store._compute_checksum(frontmatter.dumps(post)),
                            content=content,
                        )
                    
                    audit.log(
                        document_id=item_id,
                        action="restore",
                        old_data=last_entry.get("new_data"),
                        new_data=old_data,
                        actor="user",
                        item_type="entity",
                        item_name=metadata.get("name") or metadata.get("title"),
                    )
                    
                    return {"success": True, "message": "Entity metadata restored", "action": "undo_update"}
            
            raise HTTPException(status_code=400, detail="No previous metadata to restore")
        
        elif action == "delete" and item_type == "relationship":
            # Re-create the relationship from snapshot
            if isinstance(old_data, dict) and old_data.get("properties"):
                props = old_data["properties"]
                source_id = old_data.get("source_id")
                target_id = old_data.get("target_id")
                
                if source_id and target_id:
                    rel_type = props.get("type", "related_to")
                    from soml.mcp import tools as mcp_tools
                    result = mcp_tools.add_relationship(
                        source_id=source_id,
                        target_id=target_id,
                        rel_type=rel_type,
                        properties=props,
                        allow_multiple=True,
                    )
                    
                    if result.action == "created":
                        audit.log(
                            document_id=result.relationship_id or item_id,
                            action="restore",
                            old_data=None,
                            new_data=old_data,
                            actor="user",
                            item_type="relationship",
                            item_name=f"Restored relationship ({rel_type})",
                        )
                        return {"success": True, "message": "Relationship restored", "action": "undo_delete", "relationship_id": result.relationship_id}
            
            raise HTTPException(status_code=400, detail="No snapshot data to restore relationship from")
        
        else:
            raise HTTPException(status_code=400, detail=f"Undo not supported for action '{action}' on type '{item_type}'")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error undoing action for {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# Run with uvicorn
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

