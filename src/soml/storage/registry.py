"""
SQLite Registry Store - Document index and metadata.

The registry maintains:
- Document ID → file path mapping
- Content checksums for change detection
- Parent-child relationships for hierarchical documents
- Full-text search index
- Last indexed timestamp

This is a DERIVED cache - if SQLite is lost, it can be rebuilt from markdown.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import UUID

from soml.core.config import settings, get_logger
from soml.core.types import EntityType, DocumentType

logger = get_logger("storage.registry")


class RegistryStore:
    """
    SQLite registry for document indexing and metadata.
    
    Tables:
    - documents: Main document registry
    - document_fts: Full-text search virtual table
    """
    
    def __init__(self, db_path: Path | None = None):
        """Initialize the registry store."""
        self.db_path = db_path or settings.registry_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            # Main documents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    name TEXT,
                    parent_id TEXT,
                    checksum TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_indexed TEXT NOT NULL,
                    metadata TEXT,
                    document_type TEXT,
                    parent_entity_id TEXT,
                    parent_entity_type TEXT,
                    locked INTEGER DEFAULT 0,
                    FOREIGN KEY (parent_id) REFERENCES documents(id)
                )
            """)
            
            # Try to add new columns if they don't exist (for existing DBs)
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN document_type TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN parent_entity_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN parent_entity_type TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN locked INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN parent_relationship_id TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_parent ON documents(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_parent_entity ON documents(parent_entity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_parent_relationship ON documents(parent_relationship_id)")
            
            # Full-text search table (standalone, not synced with documents)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
                    id,
                    name,
                    content,
                    tags
                )
            """)
            
            # Audit log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_data TEXT,
                    new_data TEXT,
                    timestamp TEXT NOT NULL,
                    actor TEXT DEFAULT 'system',
                    item_type TEXT,
                    item_name TEXT
                )
            """)
            
            # Add new columns to existing audit_log tables (migration-safe)
            # Must run BEFORE creating indexes on these columns
            for col, coldef in [
                ("actor", "TEXT DEFAULT 'system'"),
                ("item_type", "TEXT"),
                ("item_name", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {coldef}")
                except Exception:
                    pass  # Column already exists
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_document ON audit_log(document_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_item_type ON audit_log(item_type)")
            
            # Folders table for hierarchical document organization
            conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_folder_id TEXT,
                    owner_entity_id TEXT,
                    owner_entity_type TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (parent_folder_id) REFERENCES folders(id)
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_folder_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(owner_entity_id)")
            
            # Tags metadata table (shared pool for entities and documents)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    name TEXT PRIMARY KEY,
                    color TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Add folder_id column to documents if not exists
            try:
                conn.execute("ALTER TABLE documents ADD COLUMN folder_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def index(
        self,
        doc_id: str,
        path: Path,
        entity_type: EntityType | str,
        name: str | None,
        checksum: str,
        content: str,
        tags: list[str] | None = None,
        parent_id: str | None = None,
        metadata: dict | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        document_type: DocumentType | str | None = None,
        parent_entity_id: str | None = None,
        parent_entity_type: EntityType | str | None = None,
        parent_relationship_id: str | None = None,
        locked: bool = False,
    ) -> None:
        """
        Index a document in the registry.
        
        Creates or updates the document entry.
        """
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        now = datetime.now().isoformat()
        created = (created_at or datetime.now()).isoformat()
        updated = (updated_at or datetime.now()).isoformat()
        tags_str = ",".join(tags) if tags else ""
        metadata_str = str(metadata) if metadata else ""
        doc_type_str = document_type.value if isinstance(document_type, DocumentType) else document_type
        parent_entity_type_str = parent_entity_type.value if isinstance(parent_entity_type, EntityType) else parent_entity_type
        locked_int = 1 if locked else 0
        
        with self._get_connection() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            
            if existing:
                # Update
                conn.execute("""
                    UPDATE documents SET
                        path = ?,
                        type = ?,
                        name = ?,
                        parent_id = ?,
                        checksum = ?,
                        updated_at = ?,
                        last_indexed = ?,
                        metadata = ?,
                        document_type = ?,
                        parent_entity_id = ?,
                        parent_entity_type = ?,
                        parent_relationship_id = ?,
                        locked = ?
                    WHERE id = ?
                """, (str(path), type_str, name, parent_id, checksum, updated, now, metadata_str, 
                      doc_type_str, parent_entity_id, parent_entity_type_str, parent_relationship_id, locked_int, doc_id))
            else:
                # Insert
                conn.execute("""
                    INSERT INTO documents (id, path, type, name, parent_id, checksum, created_at, updated_at, last_indexed, metadata, document_type, parent_entity_id, parent_entity_type, parent_relationship_id, locked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (doc_id, str(path), type_str, name, parent_id, checksum, created, updated, now, metadata_str,
                      doc_type_str, parent_entity_id, parent_entity_type_str, parent_relationship_id, locked_int))
            
            # Update FTS
            conn.execute("DELETE FROM document_fts WHERE id = ?", (doc_id,))
            conn.execute(
                "INSERT INTO document_fts (id, name, content, tags) VALUES (?, ?, ?, ?)",
                (doc_id, name or "", content, tags_str)
            )
            
            conn.commit()
            logger.debug(f"Indexed document {doc_id} at {path}")
    
    def get(self, doc_id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_by_path(self, path: Path) -> dict[str, Any] | None:
        """Get a document by file path."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE path = ?", (str(path),)
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def delete(self, doc_id: str) -> bool:
        """Delete a document from the registry."""
        with self._get_connection() as conn:
            # Delete from FTS
            conn.execute("DELETE FROM document_fts WHERE id = ?", (doc_id,))
            
            # Delete from main table
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted document {doc_id} from registry")
            return deleted
    
    def _escape_fts_query(self, query: str) -> str:
        """
        Escape a query string for FTS5 MATCH.
        
        FTS5 has special syntax characters that need to be escaped.
        We wrap the query in double quotes to make it a phrase search,
        which handles most special characters safely.
        """
        # Remove or escape problematic characters
        # FTS5 special chars: " ' ( ) * : ^ -
        # Escape double quotes by doubling them
        escaped = query.replace('"', '""')
        # Wrap in double quotes for phrase search (handles apostrophes, etc.)
        return f'"{escaped}"'
    
    def search(self, query: str, entity_type: EntityType | str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """
        Full-text search across documents.
        
        Returns matching documents ordered by relevance.
        """
        # Escape the query for FTS5
        fts_query = self._escape_fts_query(query)
        
        with self._get_connection() as conn:
            if entity_type:
                type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
                rows = conn.execute("""
                    SELECT d.*, bm25(document_fts) as rank
                    FROM document_fts f
                    JOIN documents d ON f.id = d.id
                    WHERE document_fts MATCH ? AND d.type = ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, type_str, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT d.*, bm25(document_fts) as rank
                    FROM document_fts f
                    JOIN documents d ON f.id = d.id
                    WHERE document_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit)).fetchall()
            
            return [dict(row) for row in rows]
    
    def list_by_type(self, entity_type: EntityType | str) -> list[dict[str, Any]]:
        """List all documents of a given type."""
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE type = ? ORDER BY updated_at DESC",
                (type_str,)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def list_children(self, parent_id: str) -> list[dict[str, Any]]:
        """List all child documents of a parent."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE parent_id = ?",
                (parent_id,)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_stale_documents(self, since: datetime) -> list[dict[str, Any]]:
        """Get documents that haven't been indexed since a given time."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE last_indexed < ?",
                (since.isoformat(),)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def has_changed(self, doc_id: str, checksum: str) -> bool:
        """Check if a document has changed based on checksum."""
        doc = self.get(doc_id)
        if not doc:
            return True  # New document
        return doc["checksum"] != checksum
    
    def rebuild_from_directory(self, data_dir: Path) -> int:
        """
        Rebuild the registry from markdown files.
        
        Returns the number of documents indexed.
        """
        from soml.storage.markdown import MarkdownStore
        
        md_store = MarkdownStore(data_dir)
        count = 0
        
        for path in md_store.list_all():
            doc = md_store.read(path)
            if not doc:
                continue
            
            metadata = doc["metadata"]
            self.index(
                doc_id=metadata.get("id", ""),
                path=path,
                entity_type=metadata.get("type", "note"),
                name=metadata.get("name") or metadata.get("title"),
                checksum=doc["checksum"],
                content=doc["content"],
                tags=metadata.get("tags", []),
                parent_id=metadata.get("parent_id"),
                created_at=datetime.fromisoformat(metadata["created_at"]) if metadata.get("created_at") else None,
                updated_at=datetime.fromisoformat(metadata["updated_at"]) if metadata.get("updated_at") else None,
            )
            count += 1
        
        logger.info(f"Rebuilt registry with {count} documents")
        return count
    
    def log_audit(
        self,
        doc_id: str,
        action: str,
        old_data: str | None = None,
        new_data: str | None = None,
        actor: str = "system",
        item_type: str | None = None,
        item_name: str | None = None,
    ) -> None:
        """Log an audit entry with actor and item metadata."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_log (document_id, action, old_data, new_data, timestamp, actor, item_type, item_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, action, old_data, new_data, datetime.now().isoformat(), actor, item_type, item_name))
            conn.commit()
    
    def get_audit_history(self, doc_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get audit history for a specific item."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log 
                WHERE document_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (doc_id, limit)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_recent_activity(
        self,
        limit: int = 50,
        item_type: str | None = None,
        actor: str | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent audit activity across all items.
        
        Args:
            limit: Max entries to return
            item_type: Filter by type (entity, document, relationship)
            actor: Filter by actor (user, agent, system)
            since: ISO timestamp to filter from
        """
        with self._get_connection() as conn:
            conditions = []
            params: list[Any] = []
            
            if item_type:
                conditions.append("item_type = ?")
                params.append(item_type)
            if actor:
                conditions.append("actor = ?")
                params.append(actor)
            if since:
                conditions.append("timestamp >= ?")
                params.append(since)
            
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            rows = conn.execute(f"""
                SELECT * FROM audit_log
                {where}
                ORDER BY timestamp DESC
                LIMIT ?
            """, (*params, limit)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_entity_activity(self, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Get all activity related to an entity, including its documents.
        """
        with self._get_connection() as conn:
            # Get document IDs belonging to this entity
            doc_rows = conn.execute(
                "SELECT id FROM documents WHERE parent_entity_id = ?", (entity_id,)
            ).fetchall()
            doc_ids = [r["id"] for r in doc_rows]
            
            # Build IN clause for entity + its documents
            all_ids = [entity_id] + doc_ids
            placeholders = ",".join(["?"] * len(all_ids))
            
            rows = conn.execute(f"""
                SELECT * FROM audit_log
                WHERE document_id IN ({placeholders})
                ORDER BY timestamp DESC
                LIMIT ?
            """, (*all_ids, limit)).fetchall()
            
            return [dict(row) for row in rows]
    
    # ============================================
    # Document-specific methods
    # ============================================
    
    def list_entity_documents(self, entity_id: str) -> list[dict[str, Any]]:
        """
        List all documents attached to a specific entity.
        
        Returns documents sorted with general_info first, then by name.
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM documents 
                WHERE parent_entity_id = ? 
                ORDER BY 
                    CASE WHEN document_type = 'general_info' THEN 0 ELSE 1 END,
                    name ASC
            """, (entity_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def list_relationship_documents(self, relationship_id: str) -> list[dict[str, Any]]:
        """
        List all documents attached to a specific relationship.
        
        Returns documents sorted by updated_at descending.
        """
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM documents 
                WHERE parent_relationship_id = ? 
                ORDER BY updated_at DESC
            """, (relationship_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_general_info_document(self, entity_id: str) -> dict[str, Any] | None:
        """Get the General Info document for an entity."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM documents 
                WHERE parent_entity_id = ? AND document_type = 'general_info'
                LIMIT 1
            """, (entity_id,)).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def list_documents_by_type(self, document_type: DocumentType | str) -> list[dict[str, Any]]:
        """List all documents of a specific document type."""
        doc_type_str = document_type.value if isinstance(document_type, DocumentType) else document_type
        
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE document_type = ? ORDER BY updated_at DESC",
                (doc_type_str,)
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    def list_all_documents(self) -> list[dict[str, Any]]:
        """List all document-type entities (not entity types)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE type = 'document' ORDER BY updated_at DESC"
            ).fetchall()
            
            return [dict(row) for row in rows]
    
    # ============================================
    # Folder Management Methods
    # ============================================
    
    def create_folder(
        self,
        name: str,
        parent_folder_id: str | None = None,
        owner_entity_id: str | None = None,
        owner_entity_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new folder.
        
        Args:
            name: Folder name
            parent_folder_id: Parent folder ID for nesting
            owner_entity_id: Entity that owns this folder
            owner_entity_type: Type of the owning entity
        
        Returns:
            The created folder record
        """
        from uuid import uuid4
        
        folder_id = str(uuid4())
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO folders (id, name, parent_folder_id, owner_entity_id, owner_entity_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (folder_id, name, parent_folder_id, owner_entity_id, owner_entity_type, now, now))
            conn.commit()
            
            logger.debug(f"Created folder {folder_id}: {name}")
            
            return {
                "id": folder_id,
                "name": name,
                "parent_folder_id": parent_folder_id,
                "owner_entity_id": owner_entity_id,
                "owner_entity_type": owner_entity_type,
                "created_at": now,
                "updated_at": now,
            }
    
    def get_folder(self, folder_id: str) -> dict[str, Any] | None:
        """Get a folder by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM folders WHERE id = ?", (folder_id,)
            ).fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_folder_by_path(
        self,
        path: str,
        owner_entity_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a folder by its path (e.g., "/Projects/Active").
        
        Args:
            path: Folder path with "/" separator
            owner_entity_id: Optional entity scope
        
        Returns:
            Folder record or None
        """
        if path == "/" or path == "":
            return None  # Root has no record
        
        parts = [p for p in path.split("/") if p]
        current_folder = None
        
        with self._get_connection() as conn:
            for part in parts:
                if current_folder:
                    row = conn.execute("""
                        SELECT * FROM folders 
                        WHERE name = ? AND parent_folder_id = ?
                    """, (part, current_folder["id"])).fetchone()
                else:
                    # Root level - check owner_entity_id
                    if owner_entity_id:
                        row = conn.execute("""
                            SELECT * FROM folders 
                            WHERE name = ? AND parent_folder_id IS NULL AND owner_entity_id = ?
                        """, (part, owner_entity_id)).fetchone()
                    else:
                        row = conn.execute("""
                            SELECT * FROM folders 
                            WHERE name = ? AND parent_folder_id IS NULL AND owner_entity_id IS NULL
                        """, (part,)).fetchone()
                
                if not row:
                    return None
                current_folder = dict(row)
        
        return current_folder
    
    def list_folders(
        self,
        parent_folder_id: str | None = None,
        owner_entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List folders, optionally filtered by parent or owner.
        
        Args:
            parent_folder_id: Filter by parent folder (None = root level)
            owner_entity_id: Filter by owning entity
        
        Returns:
            List of folder records
        """
        with self._get_connection() as conn:
            if parent_folder_id:
                rows = conn.execute("""
                    SELECT * FROM folders 
                    WHERE parent_folder_id = ?
                    ORDER BY name ASC
                """, (parent_folder_id,)).fetchall()
            elif owner_entity_id:
                rows = conn.execute("""
                    SELECT * FROM folders 
                    WHERE owner_entity_id = ? AND parent_folder_id IS NULL
                    ORDER BY name ASC
                """, (owner_entity_id,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM folders 
                    WHERE parent_folder_id IS NULL AND owner_entity_id IS NULL
                    ORDER BY name ASC
                """).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_folder_path(self, folder_id: str) -> str:
        """
        Get the full path for a folder (e.g., "/Projects/Active").
        
        Returns "/" for root-level folders.
        """
        parts = []
        current_id = folder_id
        
        with self._get_connection() as conn:
            while current_id:
                row = conn.execute(
                    "SELECT * FROM folders WHERE id = ?", (current_id,)
                ).fetchone()
                
                if not row:
                    break
                
                folder = dict(row)
                parts.append(folder["name"])
                current_id = folder.get("parent_folder_id")
        
        parts.reverse()
        return "/" + "/".join(parts) if parts else "/"
    
    def move_folder(self, folder_id: str, new_parent_id: str | None) -> bool:
        """
        Move a folder to a new parent.
        
        Args:
            folder_id: Folder to move
            new_parent_id: New parent folder ID (None = root level)
        
        Returns:
            True if successful
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE folders 
                SET parent_folder_id = ?, updated_at = ?
                WHERE id = ?
            """, (new_parent_id, now, folder_id))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        """Rename a folder."""
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE folders 
                SET name = ?, updated_at = ?
                WHERE id = ?
            """, (new_name, now, folder_id))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def delete_folder(self, folder_id: str, recursive: bool = False) -> bool:
        """
        Delete a folder.
        
        Args:
            folder_id: Folder to delete
            recursive: If True, delete subfolders and move documents to parent.
                       If False, fail if folder has contents.
        
        Returns:
            True if deleted successfully
        """
        with self._get_connection() as conn:
            # Check for subfolders
            subfolders = conn.execute(
                "SELECT id FROM folders WHERE parent_folder_id = ?", (folder_id,)
            ).fetchall()
            
            # Check for documents
            documents = conn.execute(
                "SELECT id FROM documents WHERE folder_id = ?", (folder_id,)
            ).fetchall()
            
            if (subfolders or documents) and not recursive:
                logger.warning(f"Cannot delete folder {folder_id}: has contents and recursive=False")
                return False
            
            # Get parent for moving documents
            folder = self.get_folder(folder_id)
            parent_id = folder.get("parent_folder_id") if folder else None
            
            if recursive:
                # Recursively delete subfolders
                for sf in subfolders:
                    self.delete_folder(sf["id"], recursive=True)
                
                # Move documents to parent folder
                conn.execute("""
                    UPDATE documents 
                    SET folder_id = ?
                    WHERE folder_id = ?
                """, (parent_id, folder_id))
            
            # Delete the folder
            cursor = conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            conn.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted folder {folder_id}")
            
            return deleted
    
    def update_document_folder(self, doc_id: str, folder_id: str | None) -> bool:
        """
        Update the folder assignment for a document.
        
        Args:
            doc_id: Document ID
            folder_id: New folder ID (None = root level)
        
        Returns:
            True if update succeeded
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE documents SET folder_id = ?, updated_at = ? WHERE id = ?",
                (folder_id, datetime.now().isoformat(), doc_id)
            )
            conn.commit()
            
            updated = cursor.rowcount > 0
            if updated:
                logger.debug(f"Updated document {doc_id} folder to {folder_id}")
            
            return updated
    
    def get_folder_contents(self, folder_id: str | None) -> dict[str, Any]:
        """
        Get all contents of a folder (subfolders and documents).
        
        Args:
            folder_id: Folder ID (None = root level)
        
        Returns:
            Dict with 'folders' and 'documents' lists
        """
        with self._get_connection() as conn:
            if folder_id:
                folders = conn.execute("""
                    SELECT * FROM folders 
                    WHERE parent_folder_id = ?
                    ORDER BY name ASC
                """, (folder_id,)).fetchall()
                
                documents = conn.execute("""
                    SELECT * FROM documents 
                    WHERE folder_id = ?
                    ORDER BY name ASC
                """, (folder_id,)).fetchall()
            else:
                folders = conn.execute("""
                    SELECT * FROM folders 
                    WHERE parent_folder_id IS NULL
                    ORDER BY name ASC
                """).fetchall()
                
                documents = conn.execute("""
                    SELECT * FROM documents 
                    WHERE folder_id IS NULL
                    ORDER BY name ASC
                """).fetchall()
            
            return {
                "folders": [dict(row) for row in folders],
                "documents": [dict(row) for row in documents],
            }
    
    def get_folder_tree(
        self,
        root_folder_id: str | None = None,
        owner_entity_id: str | None = None,
        include_documents: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get a hierarchical folder tree.
        
        Args:
            root_folder_id: Start from this folder (None = root)
            owner_entity_id: Filter by owning entity
            include_documents: Include document counts
        
        Returns:
            List of folder dicts with 'children' nested
        """
        def build_tree(parent_id: str | None) -> list[dict[str, Any]]:
            folders = self.list_folders(parent_folder_id=parent_id, owner_entity_id=owner_entity_id if not parent_id else None)
            
            result = []
            for folder in folders:
                node = dict(folder)
                node["children"] = build_tree(folder["id"])
                
                if include_documents:
                    # Count documents in this folder
                    with self._get_connection() as conn:
                        count = conn.execute(
                            "SELECT COUNT(*) as cnt FROM documents WHERE folder_id = ?",
                            (folder["id"],)
                        ).fetchone()
                        node["document_count"] = count["cnt"] if count else 0
                
                result.append(node)
            
            return result
        
        return build_tree(root_folder_id)
    
    def move_document_to_folder(self, doc_id: str, folder_id: str | None) -> bool:
        """
        Move a document to a folder.
        
        Args:
            doc_id: Document ID
            folder_id: Target folder ID (None = root level)
        
        Returns:
            True if successful
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE documents 
                SET folder_id = ?, updated_at = ?
                WHERE id = ?
            """, (folder_id, now, doc_id))
            conn.commit()
            
            return cursor.rowcount > 0
    
    # ============================================
    # Tag Management Methods
    # ============================================
    
    def get_all_tags(self) -> list[dict[str, Any]]:
        """Get all tags with usage counts."""
        with self._get_connection() as conn:
            # Get tags from metadata table
            rows = conn.execute("""
                SELECT * FROM tags ORDER BY name ASC
            """).fetchall()
            
            return [dict(row) for row in rows]
    
    def search_tags(self, prefix: str) -> list[dict[str, Any]]:
        """Search tags by name prefix for autocomplete."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM tags 
                WHERE name LIKE ?
                ORDER BY name ASC
                LIMIT 20
            """, (f"{prefix}%",)).fetchall()
            
            return [dict(row) for row in rows]
    
    def upsert_tag(
        self,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create or update a tag.
        
        Args:
            name: Tag name (primary key)
            color: Optional hex color
            description: Optional description
        
        Returns:
            The tag record
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            existing = conn.execute(
                "SELECT * FROM tags WHERE name = ?", (name,)
            ).fetchone()
            
            if existing:
                # Update if new values provided
                if color is not None or description is not None:
                    conn.execute("""
                        UPDATE tags 
                        SET color = COALESCE(?, color), description = COALESCE(?, description)
                        WHERE name = ?
                    """, (color, description, name))
                    conn.commit()
            else:
                conn.execute("""
                    INSERT INTO tags (name, color, description, created_at)
                    VALUES (?, ?, ?, ?)
                """, (name, color, description, now))
                conn.commit()
                
                logger.debug(f"Created tag: {name}")
            
            return {
                "name": name,
                "color": color or (existing["color"] if existing else None),
                "description": description or (existing["description"] if existing else None),
                "created_at": existing["created_at"] if existing else now,
            }
    
    def delete_tag(self, name: str) -> bool:
        """Delete a tag from the metadata table."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM tags WHERE name = ?", (name,))
            conn.commit()
            
            return cursor.rowcount > 0

