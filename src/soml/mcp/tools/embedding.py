"""
MCP Tools - Embedding generation and management.

Tools for vector embeddings:
- generate_and_store_embedding: Generate embedding for an entity
- generate_and_store_document_embedding: Generate embedding for a document
- refresh_entity_embedding: Refresh entity embedding
- refresh_all_embeddings: Batch refresh all embeddings
"""

from soml.core.types import EntityType
from soml.mcp.tools.base import (
    _get_graph_store,
    _get_md_store,
    _get_registry,
    logger,
)


def _generate_embedding_sync(text: str) -> list[float] | None:
    """
    Generate embedding synchronously, handling event loop issues.
    
    Works whether called from main thread, async context, or background thread.
    """
    from openai import OpenAI
    from soml.core.config import settings
    
    try:
        # Use sync OpenAI client to avoid async event loop issues
        client = OpenAI(api_key=settings.openai_api_key)
        
        response = client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text[:8000],  # Truncate to avoid token limits
        )
        
        return response.data[0].embedding
        
    except Exception as e:
        logger.error(f"Sync embedding generation failed: {e}")
        return None


def _build_embedding_text(entity_id: str) -> str | None:
    """Build text for embedding from entity data AND all its documents."""
    registry = _get_registry()
    md_store = _get_md_store()
    
    # Get entity
    entity = registry.get(str(entity_id))
    if not entity:
        return None
    
    parts = []
    
    # Entity name/title
    name = entity.get("name") or entity.get("title") or entity.get("name")
    if name:
        parts.append(f"Name: {name}")
    
    # Entity type
    parts.append(f"Type: {entity.get('type', 'unknown')}")
    
    # Get full metadata from markdown
    md_doc = md_store.read_by_id(entity_id, entity.get("type"))
    if md_doc:
        metadata = md_doc.get("metadata", {})
        
        # Disambiguator
        if metadata.get("disambiguator"):
            parts.append(f"Context: {metadata['disambiguator']}")
        
        # Status (for projects/goals)
        if metadata.get("status"):
            parts.append(f"Status: {metadata['status']}")
    
    # Get ALL documents for this entity (not just General Info)
    all_docs = registry.list_entity_documents(str(entity_id))
    
    for doc in all_docs:
        doc_content = md_store.read_document(doc.get("id"))
        if doc_content:
            content = doc_content.get("content", "")
            doc_type = doc.get("document_type", "note")
            doc_name = doc.get("name", "Document")
            
            if content:
                # Include document title and content
                parts.append(f"\n--- {doc_type.upper()}: {doc_name} ---")
                parts.append(content[:2000])  # Cap each doc at 2000 chars
    
    # Cap total at ~6000 chars to stay within embedding token limits
    full_text = "\n".join(parts)
    return full_text[:6000] if full_text else None


def generate_and_store_embedding(
    entity_id: str,
    text: str | None = None,
) -> bool:
    """
    Generate and store an embedding for an entity.
    
    If text is not provided, generates embedding from the entity's
    name, description, disambiguator, and General Info document.
    
    Args:
        entity_id: Entity ID
        text: Optional custom text to embed (otherwise auto-generated)
    
    Returns:
        True if successful, False otherwise
    """
    graph_store = _get_graph_store()
    
    # If no text provided, build it from entity data
    if not text:
        text = _build_embedding_text(entity_id)
    
    if not text:
        logger.warning(f"No text available for embedding entity {entity_id}")
        return False
    
    try:
        # Generate embedding using sync wrapper
        embedding = _generate_embedding_sync(text)
        
        if embedding:
            # Store in Neo4j
            graph_store.store_embedding(entity_id, embedding)
            logger.info(f"Generated and stored embedding for entity {entity_id}")
            return True
        else:
            logger.warning(f"Embedding generation returned None for {entity_id}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to generate embedding for {entity_id}: {e}")
        return False


def generate_and_store_document_embedding(doc_id: str) -> bool:
    """
    Generate and store an embedding for a specific document.
    
    This creates a Document node in Neo4j with the embedding for direct document search.
    
    Args:
        doc_id: Document ID
    
    Returns:
        True if successful
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # Get document from registry
    doc = registry.get(str(doc_id))
    if not doc or doc.get("type") != "document":
        logger.warning(f"Document {doc_id} not found in registry")
        return False
    
    # Read full document content
    full_doc = md_store.read_document(doc_id)
    if not full_doc:
        logger.warning(f"Could not read document {doc_id}")
        return False
    
    content = full_doc.get("content", "")
    doc_name = doc.get("name", "Document")
    doc_type = doc.get("document_type", "note")
    parent_id = doc.get("parent_entity_id")
    
    # Build embedding text
    text = f"Document: {doc_name}\nType: {doc_type}\n\n{content}"
    text = text[:6000]  # Cap at embedding limits
    
    try:
        embedding = _generate_embedding_sync(text)
        
        if embedding:
            # Create or update Document node in Neo4j
            with graph_store.session() as session:
                session.run(
                    """
                    MERGE (d:Document:Entity {id: $id})
                    SET d.name = $name,
                        d.document_type = $doc_type,
                        d.parent_entity_id = $parent_id,
                        d.entity_type = 'document',
                        d.embedding = $embedding
                    """,
                    id=str(doc_id),
                    name=doc_name,
                    doc_type=doc_type,
                    parent_id=parent_id,
                    embedding=embedding,
                )
                
                # Create relationship to parent entity if exists
                if parent_id:
                    session.run(
                        """
                        MATCH (d:Document {id: $doc_id})
                        MATCH (e:Entity {id: $parent_id})
                        MERGE (d)-[:BELONGS_TO]->(e)
                        """,
                        doc_id=str(doc_id),
                        parent_id=parent_id,
                    )
            
            logger.info(f"Generated and stored embedding for document {doc_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to generate document embedding for {doc_id}: {e}")
        return False


def refresh_entity_embedding(entity_id: str) -> bool:
    """
    Refresh the embedding for an entity.
    
    Call this after entity content changes (new documents, updated info).
    
    Args:
        entity_id: Entity ID
    
    Returns:
        True if successful
    """
    return generate_and_store_embedding(entity_id)


def refresh_all_embeddings(entity_type: str | None = None, include_documents: bool = True) -> dict:
    """
    Refresh embeddings for all entities AND documents.
    
    This is a maintenance operation to regenerate all embeddings,
    useful after bulk imports or system updates.
    
    Args:
        entity_type: Optional type filter (person, project, etc.)
        include_documents: If True (default), also embed all documents
    
    Returns:
        Stats dict with success/failure counts for entities and documents
    """
    registry = _get_registry()
    
    stats = {
        "entities": {"total": 0, "success": 0, "failed": 0},
        "documents": {"total": 0, "success": 0, "failed": 0},
    }
    
    # Process entities
    if entity_type:
        entities = registry.list_by_type(entity_type)
    else:
        # Get all entity types (excluding documents)
        entities = []
        for etype in [EntityType.PERSON, EntityType.PROJECT, EntityType.GOAL, EntityType.EVENT, EntityType.PERIOD]:
            entities.extend(registry.list_by_type(etype))
    
    stats["entities"]["total"] = len(entities)
    
    for entity in entities:
        if generate_and_store_embedding(entity["id"]):
            stats["entities"]["success"] += 1
        else:
            stats["entities"]["failed"] += 1
    
    # Process documents
    if include_documents:
        documents = registry.list_by_type(EntityType.DOCUMENT)
        stats["documents"]["total"] = len(documents)
        
        for doc in documents:
            if generate_and_store_document_embedding(doc["id"]):
                stats["documents"]["success"] += 1
            else:
                stats["documents"]["failed"] += 1
    
    logger.info(f"Refreshed embeddings: {stats}")
    return stats


__all__ = [
    "_generate_embedding_sync",
    "_build_embedding_text",
    "generate_and_store_embedding",
    "generate_and_store_document_embedding",
    "refresh_entity_embedding",
    "refresh_all_embeddings",
]

