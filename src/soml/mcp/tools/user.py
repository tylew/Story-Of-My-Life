"""
MCP Tools - User entity tools.

Tools for managing the special user entity (is_self=True):
- get_or_create_user: Get user entity, create if not exists
- get_user_documents: Get documents owned by user entity
- store_user_note: Quick helper to store a note under user entity
- update_user: Update user entity information
"""

from uuid import uuid4

from soml.core.types import EntityType, Person, Source
from soml.mcp.tools.base import (
    _get_graph_store,
    _get_md_store,
    _get_registry,
    _create_general_info_document,
    logger,
)
from soml.mcp.tools.document import create_document
from soml.mcp.tools.folder import list_folder_contents


def get_or_create_user(name: str | None = None) -> dict:
    """
    Get the user entity (is_self=True), create if not exists.
    
    The user entity is a special Person with is_self=True that represents
    the system owner. It's used as an anchor for personal documents.
    
    Args:
        name: User's name (only used if creating new user entity)
    
    Returns:
        User entity info with:
        - id: Entity ID
        - name: User's name
        - is_self: Always True
        - existed: Whether the user entity already existed
        - error: Error message if failed
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    try:
        # Search for existing user entity (is_self=True)
        # Look through all person entities
        with registry._get_connection() as conn:
            # Search in documents table for person entities
            rows = conn.execute(
                """
                SELECT id, name, path FROM documents 
                WHERE type = 'person'
                ORDER BY created_at ASC
                """
            ).fetchall()
        
        # Check each person for is_self flag
        for row in rows:
            from pathlib import Path
            path = Path(row["path"]) if row["path"] else None
            if path and path.exists():
                entity = md_store.read(path)
                if entity and entity.get("metadata", {}).get("is_self"):
                    return {
                        "id": row["id"],
                        "name": row["name"],
                        "is_self": True,
                        "existed": True,
                    }
        
        # No user entity found - create one
        if not name:
            name = "Me"  # Default name
        
        user_id = str(uuid4())
        
        # Create Person entity
        user = Person(
            id=user_id,
            name=name,
            is_self=True,
        )
        
        # Write to markdown
        filepath = md_store.write(user)
        
        # Index in registry
        registry.index(
            doc_id=user_id,
            path=filepath,
            entity_type=EntityType.PERSON,
            name=name,
            checksum=md_store._compute_checksum(str(user.model_dump())),
            content=f"User: {name}",
        )
        
        # Upsert to graph
        graph_store.upsert_node(user)
        
        # Create General Info document
        _create_general_info_document(
            entity_id=user_id,
            entity_type=EntityType.PERSON,
            entity_name=name,
            initial_content=f"# About {name}\n\nThis is my personal knowledge base.",
            md_store=md_store,
            registry=registry,
        )
        
        logger.info(f"Created user entity '{name}' ({user_id})")
        
        return {
            "id": user_id,
            "name": name,
            "is_self": True,
            "existed": False,
        }
        
    except Exception as e:
        logger.error(f"Failed to get/create user entity: {e}")
        return {
            "id": None,
            "name": name,
            "is_self": True,
            "error": str(e),
        }


def get_user_documents(folder_path: str | None = None) -> dict:
    """
    Get documents owned by the user entity.
    
    Args:
        folder_path: Optional - filter to documents in this folder
    
    Returns:
        Dict with:
        - user_id: User entity ID
        - user_name: User's name
        - documents: List of documents
        - folder_path: Folder filter if applied
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Get user entity
        user = get_or_create_user()
        if user.get("error"):
            return {
                "user_id": None,
                "error": user["error"],
            }
        
        user_id = user["id"]
        
        # Get documents
        if folder_path:
            contents = list_folder_contents(folder_path, entity_id=user_id)
            if contents.get("error"):
                return {
                    "user_id": user_id,
                    "user_name": user["name"],
                    "error": contents["error"],
                }
            documents = contents.get("documents", [])
        else:
            # Get all user documents
            documents = registry.list_entity_documents(user_id)
            documents = [
                {
                    "id": d["id"],
                    "name": d.get("name", "Untitled"),
                    "type": d.get("document_type", "note"),
                    "updated_at": d.get("updated_at"),
                }
                for d in documents
            ]
        
        return {
            "user_id": user_id,
            "user_name": user["name"],
            "documents": documents,
            "folder_path": folder_path,
        }
        
    except Exception as e:
        logger.error(f"Failed to get user documents: {e}")
        return {
            "user_id": None,
            "error": str(e),
        }


def store_user_note(
    title: str,
    content: str,
    folder_path: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Quick helper to store a note under the user entity.
    
    Creates a new document owned by the user entity with the given
    content, folder, and tags.
    
    Args:
        title: Note title
        content: Note content (markdown)
        folder_path: Optional folder path
        tags: Optional list of tags
    
    Returns:
        Created document info with:
        - id: Document ID
        - title: Document title
        - user_id: User entity ID
        - folder_path: Folder path
        - tags: Applied tags
        - success: Whether creation succeeded
        - error: Error message if failed
    """
    try:
        # Get user entity
        user = get_or_create_user()
        if user.get("error"):
            return {
                "success": False,
                "title": title,
                "error": user["error"],
            }
        
        user_id = user["id"]
        
        # Create document under user
        result = create_document(
            title=title,
            content=content,
            folder_path=folder_path,
            parent_entity_id=user_id,
            tags=tags,
            document_type="note",
        )
        
        result["user_id"] = user_id
        return result
        
    except Exception as e:
        logger.error(f"Failed to store user note '{title}': {e}")
        return {
            "success": False,
            "title": title,
            "error": str(e),
        }


def update_user(
    name: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """
    Update user entity information.
    
    Args:
        name: New name for the user
        tags: Tags to set on the user entity
    
    Returns:
        Update result with:
        - success: Whether update succeeded
        - user_id: User entity ID
        - changes: List of changes made
        - error: Error message if failed
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    try:
        # Get user entity
        user = get_or_create_user()
        if user.get("error"):
            return {
                "success": False,
                "error": user["error"],
            }
        
        user_id = user["id"]
        changes = []
        
        # Update name if provided
        if name and name != user["name"]:
            # Read current entity
            doc_info = registry.get(user_id)
            if doc_info:
                entity = md_store.read(doc_info["path"])
                if entity:
                    # Update the entity
                    metadata = entity.get("metadata", {})
                    metadata["name"] = name
                    
                    # Create updated Person
                    updated_user = Person(
                        id=user_id,
                        name=name,
                        is_self=True,
                    )
                    
                    # Write back
                    md_store.write(updated_user)
                    
                    # Update registry
                    registry.index(
                        doc_id=user_id,
                        path=doc_info["path"],
                        entity_type=EntityType.PERSON,
                        name=name,
                        checksum=md_store._compute_checksum(str(updated_user.model_dump())),
                        content=f"User: {name}",
                    )
                    
                    # Update graph
                    graph_store.upsert_node(updated_user)
                    
                    changes.append(f"name: {user['name']} -> {name}")
        
        # Update tags if provided
        if tags is not None:
            graph_store.sync_item_tags(user_id, "entity", tags)
            changes.append(f"tags: {tags}")
        
        logger.info(f"Updated user entity: {changes}")
        
        return {
            "success": True,
            "user_id": user_id,
            "changes": changes,
        }
        
    except Exception as e:
        logger.error(f"Failed to update user entity: {e}")
        return {
            "success": False,
            "error": str(e),
        }


__all__ = [
    "get_or_create_user",
    "get_user_documents",
    "store_user_note",
    "update_user",
]

