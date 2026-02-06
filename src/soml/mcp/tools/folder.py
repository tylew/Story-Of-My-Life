"""
MCP Tools - Folder management tools.

Tools for organizing documents in hierarchical folders:
- get_folder_tree: Get folder hierarchy with document counts
- list_folder_contents: List documents and subfolders in a folder
- create_folder: Create a new folder
- move_folder: Move folder and contents to new location
- delete_folder: Delete a folder
- rename_folder: Rename a folder
"""

from soml.mcp.tools.base import (
    _get_registry,
    logger,
)


def get_folder_tree(
    root_path: str = "/",
    entity_id: str | None = None,
    include_documents: bool = True,
) -> dict:
    """
    Get folder hierarchy with document counts.
    
    Returns a nested structure for LLM to understand the organization.
    
    Args:
        root_path: Path to start from ("/" for root)
        entity_id: Optional - limit to folders owned by this entity
        include_documents: Whether to include document details
    
    Returns:
        Nested folder structure with:
        - id: Folder ID
        - name: Folder name
        - path: Full path (e.g., "/projects/acme")
        - document_count: Number of documents in this folder
        - documents: List of documents (if include_documents=True)
        - children: Nested subfolders
    """
    registry = _get_registry()
    
    # Get root folder ID if path specified
    root_folder_id = None
    if root_path and root_path != "/":
        folder = registry.get_folder_by_path(root_path, entity_id)
        if not folder:
            return {
                "error": f"Folder not found: {root_path}",
                "folders": [],
            }
        root_folder_id = folder["id"]
    
    # Get tree from registry
    tree = registry.get_folder_tree(
        root_folder_id=root_folder_id,
        owner_entity_id=entity_id,
        include_documents=include_documents,
    )
    
    # Add paths to each folder
    def add_paths(folders: list, parent_path: str = "") -> list:
        result = []
        for folder in folders:
            folder_path = f"{parent_path}/{folder['name']}"
            item = {
                "id": folder["id"],
                "name": folder["name"],
                "path": folder_path,
                "document_count": folder.get("document_count", 0),
            }
            if include_documents:
                item["documents"] = folder.get("documents", [])
            if folder.get("children"):
                item["children"] = add_paths(folder["children"], folder_path)
            else:
                item["children"] = []
            result.append(item)
        return result
    
    return {
        "root_path": root_path,
        "entity_id": entity_id,
        "folders": add_paths(tree),
    }


def list_folder_contents(
    folder_path: str = "/",
    entity_id: str | None = None,
) -> dict:
    """
    List documents and subfolders in a folder.
    
    Args:
        folder_path: Folder path (e.g., "/projects/acme")
        entity_id: Optional - entity that owns the folder
    
    Returns:
        Dict with:
        - path: Folder path
        - folders: List of subfolders (id, name, document_count)
        - documents: List of documents (id, name, type, updated_at)
    """
    registry = _get_registry()
    
    # Resolve folder
    folder_id = None
    if folder_path and folder_path != "/":
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return {
                "path": folder_path,
                "error": f"Folder not found: {folder_path}",
                "folders": [],
                "documents": [],
            }
        folder_id = folder["id"]
    
    # Get contents
    contents = registry.get_folder_contents(folder_id)
    
    return {
        "path": folder_path,
        "folders": [
            {
                "id": f["id"],
                "name": f["name"],
                "document_count": _count_folder_documents(f["id"], registry),
            }
            for f in contents.get("folders", [])
        ],
        "documents": [
            {
                "id": d["id"],
                "name": d.get("name", "Untitled"),
                "type": d.get("document_type", "note"),
                "updated_at": d.get("updated_at"),
            }
            for d in contents.get("documents", [])
        ],
    }


def create_folder(
    name: str,
    parent_path: str = "/",
    entity_id: str | None = None,
) -> dict:
    """
    Create a new folder.
    
    Args:
        name: Folder name
        parent_path: Path of parent folder ("/" for root level)
        entity_id: Optional - entity that will own this folder
    
    Returns:
        Created folder info with:
        - id: Folder ID
        - name: Folder name
        - path: Full path
        - success: Whether creation succeeded
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Resolve parent folder
        parent_folder_id = None
        if parent_path and parent_path != "/":
            parent = registry.get_folder_by_path(parent_path, entity_id)
            if not parent:
                return {
                    "success": False,
                    "error": f"Parent folder not found: {parent_path}",
                }
            parent_folder_id = parent["id"]
        
        # Check if folder already exists
        existing = registry.list_folders(parent_folder_id=parent_folder_id, owner_entity_id=entity_id)
        if any(f["name"] == name for f in existing):
            existing_folder = next(f for f in existing if f["name"] == name)
            return {
                "id": existing_folder["id"],
                "name": name,
                "path": f"{parent_path.rstrip('/')}/{name}",
                "success": True,
                "existed": True,
            }
        
        # Create folder
        folder = registry.create_folder(
            name=name,
            parent_folder_id=parent_folder_id,
            owner_entity_id=entity_id,
        )
        
        full_path = f"{parent_path.rstrip('/')}/{name}"
        logger.info(f"Created folder '{name}' at {full_path}")
        
        return {
            "id": folder["id"],
            "name": name,
            "path": full_path,
            "success": True,
            "existed": False,
        }
        
    except Exception as e:
        logger.error(f"Failed to create folder '{name}': {e}")
        return {
            "success": False,
            "error": str(e),
        }


def move_folder(
    folder_path: str,
    new_parent_path: str,
    entity_id: str | None = None,
) -> dict:
    """
    Move folder and all contents to new location.
    
    Args:
        folder_path: Current path of folder to move
        new_parent_path: Path of new parent folder
        entity_id: Optional - entity that owns the folders
    
    Returns:
        Move result with:
        - success: Whether move succeeded
        - old_path: Previous path
        - new_path: New path
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Resolve source folder
        source = registry.get_folder_by_path(folder_path, entity_id)
        if not source:
            return {
                "success": False,
                "old_path": folder_path,
                "error": f"Folder not found: {folder_path}",
            }
        
        # Resolve target parent
        new_parent_id = None
        if new_parent_path and new_parent_path != "/":
            target = registry.get_folder_by_path(new_parent_path, entity_id)
            if not target:
                return {
                    "success": False,
                    "old_path": folder_path,
                    "error": f"Target folder not found: {new_parent_path}",
                }
            new_parent_id = target["id"]
            
            # Prevent moving folder into itself or its children
            if _is_descendant(source["id"], new_parent_id, registry):
                return {
                    "success": False,
                    "old_path": folder_path,
                    "error": "Cannot move folder into itself or its descendants",
                }
        
        # Move folder
        success = registry.move_folder(source["id"], new_parent_id)
        
        if success:
            new_path = f"{new_parent_path.rstrip('/')}/{source['name']}"
            logger.info(f"Moved folder from '{folder_path}' to '{new_path}'")
            return {
                "success": True,
                "old_path": folder_path,
                "new_path": new_path,
            }
        else:
            return {
                "success": False,
                "old_path": folder_path,
                "error": "Move operation failed",
            }
        
    except Exception as e:
        logger.error(f"Failed to move folder '{folder_path}': {e}")
        return {
            "success": False,
            "old_path": folder_path,
            "error": str(e),
        }


def delete_folder(
    folder_path: str,
    recursive: bool = False,
    entity_id: str | None = None,
) -> dict:
    """
    Delete a folder.
    
    Args:
        folder_path: Path of folder to delete
        recursive: If True, delete folder and all contents; 
                   if False, folder must be empty
        entity_id: Optional - entity that owns the folder
    
    Returns:
        Delete result with:
        - success: Whether delete succeeded
        - path: Deleted folder path
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Resolve folder
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return {
                "success": False,
                "path": folder_path,
                "error": f"Folder not found: {folder_path}",
            }
        
        # Delete folder
        success = registry.delete_folder(folder["id"], recursive=recursive)
        
        if success:
            logger.info(f"Deleted folder '{folder_path}'")
            return {
                "success": True,
                "path": folder_path,
            }
        else:
            return {
                "success": False,
                "path": folder_path,
                "error": "Folder is not empty. Use recursive=True to delete with contents.",
            }
        
    except Exception as e:
        logger.error(f"Failed to delete folder '{folder_path}': {e}")
        return {
            "success": False,
            "path": folder_path,
            "error": str(e),
        }


def rename_folder(
    folder_path: str,
    new_name: str,
    entity_id: str | None = None,
) -> dict:
    """
    Rename a folder.
    
    Args:
        folder_path: Path of folder to rename
        new_name: New name for the folder
        entity_id: Optional - entity that owns the folder
    
    Returns:
        Rename result with:
        - success: Whether rename succeeded
        - old_path: Previous path
        - new_path: New path
        - error: Error message if failed
    """
    registry = _get_registry()
    
    try:
        # Resolve folder
        folder = registry.get_folder_by_path(folder_path, entity_id)
        if not folder:
            return {
                "success": False,
                "old_path": folder_path,
                "error": f"Folder not found: {folder_path}",
            }
        
        # Get parent path
        parent_id = folder.get("parent_folder_id")
        if parent_id:
            parent_path = registry.get_folder_path(parent_id)
        else:
            parent_path = ""
        
        # Update folder name
        with registry._get_connection() as conn:
            from datetime import datetime
            conn.execute(
                "UPDATE folders SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, datetime.now().isoformat(), folder["id"])
            )
            conn.commit()
        
        new_path = f"{parent_path}/{new_name}"
        logger.info(f"Renamed folder from '{folder_path}' to '{new_path}'")
        
        return {
            "success": True,
            "old_path": folder_path,
            "new_path": new_path,
        }
        
    except Exception as e:
        logger.error(f"Failed to rename folder '{folder_path}': {e}")
        return {
            "success": False,
            "old_path": folder_path,
            "error": str(e),
        }


# ============================================
# Helper Functions
# ============================================

def _count_folder_documents(folder_id: str, registry) -> int:
    """Count documents in a folder (not recursive)."""
    contents = registry.get_folder_contents(folder_id)
    return len(contents.get("documents", []))


def _is_descendant(ancestor_id: str, potential_descendant_id: str, registry) -> bool:
    """Check if potential_descendant_id is a descendant of ancestor_id."""
    if ancestor_id == potential_descendant_id:
        return True
    
    # Walk up from potential descendant
    current_id = potential_descendant_id
    while current_id:
        folder = registry.get_folder(current_id)
        if not folder:
            break
        parent_id = folder.get("parent_folder_id")
        if parent_id == ancestor_id:
            return True
        current_id = parent_id
    
    return False


__all__ = [
    "get_folder_tree",
    "list_folder_contents",
    "create_folder",
    "move_folder",
    "delete_folder",
    "rename_folder",
]

