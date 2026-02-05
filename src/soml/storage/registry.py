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
            
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_parent ON documents(parent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_document_type ON documents(document_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_parent_entity ON documents(parent_entity_id)")
            
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
                    timestamp TEXT NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_document ON audit_log(document_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            
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
                        locked = ?
                    WHERE id = ?
                """, (str(path), type_str, name, parent_id, checksum, updated, now, metadata_str, 
                      doc_type_str, parent_entity_id, parent_entity_type_str, locked_int, doc_id))
            else:
                # Insert
                conn.execute("""
                    INSERT INTO documents (id, path, type, name, parent_id, checksum, created_at, updated_at, last_indexed, metadata, document_type, parent_entity_id, parent_entity_type, locked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (doc_id, str(path), type_str, name, parent_id, checksum, created, updated, now, metadata_str,
                      doc_type_str, parent_entity_id, parent_entity_type_str, locked_int))
            
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
    
    def log_audit(self, doc_id: str, action: str, old_data: str | None = None, new_data: str | None = None) -> None:
        """Log an audit entry."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_log (document_id, action, old_data, new_data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, action, old_data, new_data, datetime.now().isoformat()))
            conn.commit()
    
    def get_audit_history(self, doc_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get audit history for a document."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log 
                WHERE document_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (doc_id, limit)).fetchall()
            
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

