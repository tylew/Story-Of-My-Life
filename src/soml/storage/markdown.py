"""
Markdown Store - Canonical source of truth for all documents.

All entities are stored as markdown files with YAML frontmatter.
This is the primary data format - all other stores (SQLite, Neo4j)
are derived indices that can be rebuilt from markdown.

File Format:
---
id: uuid
type: person | project | goal | event | note | memory
created_at: ISO timestamp
updated_at: ISO timestamp
source: user | agent | import
confidence: 0.0-1.0
links: [list of related document ids]
tags: [topic tags]
---

# Title

Content with [[wikilinks|display text]] to other documents.
"""

import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import frontmatter
import yaml

from soml.core.config import settings, get_logger
from soml.core.types import (
    Document,
    DocumentType,
    EmploymentRecord,
    Entity,
    EntityType,
    Event,
    Goal,
    Memory,
    Note,
    Period,
    Person,
    Project,
    Source,
)

logger = get_logger("storage.markdown")


class MarkdownStore:
    """
    Markdown file store - the canonical source of truth.
    
    Documents are organized by type:
    - people/
    - projects/
    - goals/
    - events/
    - notes/
    - memories/
    """
    
    def __init__(self, data_dir: Path | None = None):
        """Initialize the markdown store."""
        self.data_dir = data_dir or settings.data_dir
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for subdir in ["people", "projects", "goals", "events", "notes", "memories", "periods", "documents", ".deleted", ".index"]:
            (self.data_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    def _get_directory(self, entity_type: EntityType | str) -> Path:
        """Get the directory for a given entity type."""
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        # Proper pluralization
        plural_map = {
            "person": "people",
            "memory": "memories",
            "goal": "goals",
            "project": "projects",
            "event": "events",
            "note": "notes",
            "period": "periods",
            "document": "documents",
        }
        plural = plural_map.get(type_str, f"{type_str}s")
        return self.data_dir / plural
    
    def _slugify(self, name: str) -> str:
        """Convert a name to a filesystem-safe slug."""
        # Convert to lowercase
        slug = name.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        return slug or "untitled"
    
    def _compute_checksum(self, content: str) -> str:
        """Compute SHA256 checksum of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _entity_to_frontmatter(self, entity: Entity) -> dict[str, Any]:
        """Convert an entity to frontmatter dictionary."""
        # Base frontmatter
        fm = {
            "id": str(entity.id),
            "type": entity.entity_type,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
            "source": entity.source.value if hasattr(entity.source, 'value') else entity.source,
            "needs_review": entity.needs_review,
            "review_reason": entity.review_reason,
            "links": [str(link) for link in entity.links],
            "tags": entity.tags,
            "custom_fields": entity.custom_fields if entity.custom_fields else {},
        }
        
        # Type-specific fields
        if isinstance(entity, Person):
            fm.update({
                "name": entity.name,
                "disambiguator": entity.disambiguator,
                "email": entity.email,
                "phone": entity.phone,
                "current_employer": entity.current_employer,
                "employment_history": [
                    {
                        "organization": emp.organization,
                        "role": emp.role,
                        "start_date": emp.start_date.isoformat() if emp.start_date else None,
                        "end_date": emp.end_date.isoformat() if emp.end_date else None,
                        "is_current": emp.is_current,
                    }
                    for emp in entity.employment_history
                ] if entity.employment_history else [],
                "last_interaction": entity.last_interaction.isoformat() if entity.last_interaction else None,
            })
        elif isinstance(entity, Project):
            fm.update({
                "name": entity.name,
                "status": entity.status,
                "stakeholders": [str(s) for s in entity.stakeholders],
                "goals": [str(g) for g in entity.goals],
                "start_date": entity.start_date.isoformat() if entity.start_date else None,
                "end_date": entity.end_date.isoformat() if entity.end_date else None,
                "last_activity": entity.last_activity.isoformat() if entity.last_activity else None,
                "children": [str(c) for c in entity.children],
            })
        elif isinstance(entity, Goal):
            fm.update({
                "title": entity.title,
                "status": entity.status,
                "target_date": entity.target_date.isoformat() if entity.target_date else None,
                "progress": entity.progress,
                "parent_project": str(entity.parent_project) if entity.parent_project else None,
                "last_progress": entity.last_progress.isoformat() if entity.last_progress else None,
            })
        elif isinstance(entity, Event):
            fm.update({
                "title": entity.title,
                "temporal_state": entity.temporal_state.value if hasattr(entity.temporal_state, 'value') else entity.temporal_state,
                "on_date": entity.on_date.isoformat() if entity.on_date else None,
                "start_time": entity.start_time.isoformat() if entity.start_time else None,
                "end_time": entity.end_time.isoformat() if entity.end_time else None,
                "location": entity.location,
                "participants": [str(p) for p in entity.participants],
                "related_projects": [str(p) for p in entity.related_projects],
                # Multi-day event support
                "parent_event_id": str(entity.parent_event_id) if entity.parent_event_id else None,
                "day_number": entity.day_number,
                "total_days": entity.total_days,
            })
        elif isinstance(entity, Note):
            fm.update({
                "title": entity.title,
                "temporal_state": entity.temporal_state.value if hasattr(entity.temporal_state, 'value') else entity.temporal_state,
                "captured_at": entity.captured_at.isoformat(),
                "referenced_time": entity.referenced_time.isoformat() if entity.referenced_time else None,
                "emotional_tone": entity.emotional_tone,
                "urgency": entity.urgency,
            })
        elif isinstance(entity, Memory):
            fm.update({
                "title": entity.title,
                "time_period_start": entity.time_period_start.isoformat() if entity.time_period_start else None,
                "time_period_end": entity.time_period_end.isoformat() if entity.time_period_end else None,
                "source_documents": [str(d) for d in entity.source_documents],
                "themes": entity.themes,
            })
        elif isinstance(entity, Period):
            fm.update({
                "name": entity.name,
                "start_date": entity.start_date.isoformat() if entity.start_date else None,
                "end_date": entity.end_date.isoformat() if entity.end_date else None,
                "related_people": [str(p) for p in entity.related_people],
                "related_projects": [str(p) for p in entity.related_projects],
                "is_complete": entity.is_complete,
            })
        elif isinstance(entity, Document):
            fm.update({
                "title": entity.title,
                "document_type": entity.document_type.value if hasattr(entity.document_type, 'value') else entity.document_type,
                "parent_entity_id": str(entity.parent_entity_id) if entity.parent_entity_id else None,
                "parent_entity_type": entity.parent_entity_type.value if entity.parent_entity_type and hasattr(entity.parent_entity_type, 'value') else entity.parent_entity_type,
                "locked": entity.locked,
                "last_edited_by": entity.last_edited_by.value if hasattr(entity.last_edited_by, 'value') else entity.last_edited_by,
            })
        
        return fm
    
    def _get_content(self, entity: Entity) -> str:
        """Get the markdown content body for an entity.
        
        Entity files now contain only a title heading. All narrative content
        lives in the associated General Info document.
        """
        if isinstance(entity, Person):
            content = f"# {entity.name}\n"
            if entity.disambiguator:
                content += f"\n_{entity.disambiguator}_\n"
        elif isinstance(entity, Project):
            content = f"# {entity.name}\n"
        elif isinstance(entity, Goal):
            content = f"# {entity.title}\n"
        elif isinstance(entity, Event):
            content = f"# {entity.title}\n"
        elif isinstance(entity, Note):
            content = ""
            if entity.title:
                content += f"# {entity.title}\n\n"
            content += entity.content
        elif isinstance(entity, Memory):
            content = f"# {entity.title}\n\n"
            content += entity.summary
        elif isinstance(entity, Period):
            content = f"# {entity.name}\n"
        elif isinstance(entity, Document):
            content = f"# {entity.title}\n\n"
            content += entity.content
        else:
            content = ""
        
        return content
    
    def _get_title(self, entity: Entity) -> str:
        """Get the title/name of an entity."""
        if isinstance(entity, Person):
            return entity.name
        elif isinstance(entity, Project):
            return entity.name
        elif isinstance(entity, Goal):
            return entity.title
        elif isinstance(entity, Event):
            return entity.title
        elif isinstance(entity, Note):
            return entity.title or f"note-{entity.id}"
        elif isinstance(entity, Memory):
            return entity.title
        elif isinstance(entity, Period):
            return entity.name
        elif isinstance(entity, Document):
            return entity.title
        return str(entity.id)
    
    def write(self, entity: Entity) -> Path:
        """
        Write an entity to a markdown file.
        
        Returns the path to the written file.
        """
        # Update timestamp
        entity.updated_at = datetime.now()
        
        # Build frontmatter and content
        fm = self._entity_to_frontmatter(entity)
        content = self._get_content(entity)
        
        # Create the markdown document
        post = frontmatter.Post(content, **fm)
        
        # Determine file path
        directory = self._get_directory(entity.entity_type)
        filename = f"{self._slugify(self._get_title(entity))}.md"
        filepath = directory / filename
        
        # Handle name collisions by appending ID
        if filepath.exists():
            existing_doc = self.read(filepath)
            if existing_doc and str(existing_doc.get("id")) != str(entity.id):
                filename = f"{self._slugify(self._get_title(entity))}-{str(entity.id)[:8]}.md"
                filepath = directory / filename
        
        # Write the file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        logger.info(f"Wrote {entity.entity_type} to {filepath}")
        return filepath
    
    def update_frontmatter(
        self, 
        entity_id: UUID | str, 
        entity_type: EntityType | str, 
        updates: dict[str, Any]
    ) -> bool:
        """
        Update frontmatter fields without rewriting the full entity.
        
        Args:
            entity_id: ID of the entity to update
            entity_type: Type of the entity
            updates: Dictionary of frontmatter fields to update
        
        Returns:
            True if successful
        """
        # Find the file
        doc = self.read_by_id(entity_id, entity_type)
        if not doc:
            logger.warning(f"Cannot update frontmatter - entity {entity_id} not found")
            return False
        
        filepath = doc.get("path")
        if not filepath:
            return False
        
        # Read the file
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)
        
        # Update frontmatter fields
        for key, value in updates.items():
            post.metadata[key] = value
        
        # Write back
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        logger.debug(f"Updated frontmatter for {entity_id}: {list(updates.keys())}")
        return True
    
    def read(self, path: Path) -> dict[str, Any] | None:
        """
        Read a markdown file and return its data.
        
        Returns a dict with 'metadata' (frontmatter) and 'content' (body).
        """
        if not path.exists():
            return None
        
        try:
            with open(path, encoding="utf-8") as f:
                post = frontmatter.load(f)
            
            return {
                "metadata": dict(post.metadata),
                "content": post.content,
                "path": path,
                "checksum": self._compute_checksum(frontmatter.dumps(post)),
            }
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return None
    
    def read_by_id(self, entity_id: UUID | str, entity_type: EntityType | str | None = None) -> dict[str, Any] | None:
        """
        Read a document by its ID.
        
        If entity_type is provided, only searches that directory.
        Otherwise, searches all directories.
        """
        id_str = str(entity_id)
        
        directories = []
        if entity_type:
            directories = [self._get_directory(entity_type)]
        else:
            directories = [
                self.data_dir / "people",
                self.data_dir / "projects",
                self.data_dir / "goals",
                self.data_dir / "events",
                self.data_dir / "notes",
                self.data_dir / "memories",
                self.data_dir / "periods",
            ]
        
        for directory in directories:
            if not directory.exists():
                continue
            for filepath in directory.glob("*.md"):
                doc = self.read(filepath)
                if doc and doc["metadata"].get("id") == id_str:
                    return doc
        
        return None
    
    def delete(self, path: Path, soft: bool = True) -> bool:
        """
        Delete a document.
        
        If soft=True (default), moves to .deleted/ folder.
        If soft=False, permanently deletes.
        """
        if not path.exists():
            return False
        
        if soft:
            # Soft delete - move to .deleted/ with timestamp
            deleted_dir = self.data_dir / ".deleted"
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_name = f"{timestamp}_{path.name}"
            shutil.move(path, deleted_dir / new_name)
            logger.info(f"Soft deleted {path} to {deleted_dir / new_name}")
        else:
            # Hard delete
            path.unlink()
            logger.info(f"Hard deleted {path}")
        
        return True
    
    def restore(self, deleted_path: Path) -> Path | None:
        """
        Restore a soft-deleted document.
        
        Returns the restored path, or None if restore failed.
        """
        if not deleted_path.exists():
            return None
        
        # Read to determine original type
        doc = self.read(deleted_path)
        if not doc:
            return None
        
        entity_type = doc["metadata"].get("type")
        if not entity_type:
            return None
        
        # Determine restore path
        original_name = deleted_path.name.split("_", 1)[1] if "_" in deleted_path.name else deleted_path.name
        restore_dir = self._get_directory(entity_type)
        restore_path = restore_dir / original_name
        
        shutil.move(deleted_path, restore_path)
        logger.info(f"Restored {deleted_path} to {restore_path}")
        return restore_path
    
    def list_all(self, entity_type: EntityType | str | None = None) -> list[Path]:
        """
        List all documents, optionally filtered by type.
        """
        if entity_type:
            directory = self._get_directory(entity_type)
            if directory.exists():
                return list(directory.glob("*.md"))
            return []
        
        # All types
        all_docs = []
        for subdir in ["people", "projects", "goals", "events", "notes", "memories", "periods", "documents"]:
            directory = self.data_dir / subdir
            if directory.exists():
                all_docs.extend(directory.rglob("*.md"))
        
        return all_docs
    
    def search(self, query: str, entity_type: EntityType | str | None = None) -> list[dict[str, Any]]:
        """
        Simple full-text search across markdown files.
        
        For production, use SQLite full-text index instead.
        """
        results = []
        query_lower = query.lower()
        
        for path in self.list_all(entity_type):
            doc = self.read(path)
            if not doc:
                continue
            
            # Search in content and metadata
            content_lower = doc["content"].lower()
            name = doc["metadata"].get("name", "").lower()
            title = doc["metadata"].get("title", "").lower()
            
            if query_lower in content_lower or query_lower in name or query_lower in title:
                results.append(doc)
        
        return results
    
    def get_checksum(self, path: Path) -> str | None:
        """Get the checksum of a file."""
        doc = self.read(path)
        return doc["checksum"] if doc else None
    
    def parse_wikilinks(self, content: str) -> list[tuple[str, str]]:
        """
        Parse wikilinks from content.
        
        Returns list of (id, display_text) tuples.
        """
        # Match [[id|display]] or [[id]]
        pattern = r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"
        matches = re.findall(pattern, content)
        
        return [(m[0], m[1] or m[0]) for m in matches]
    
    def add_wikilink(self, content: str, target_id: str, display_text: str) -> str:
        """Add a wikilink to content."""
        return content + f"\n\n[[{target_id}|{display_text}]]"
    
    # ============================================
    # Document-specific methods
    # ============================================
    
    def write_document(self, doc: Document) -> Path:
        """
        Write a Document entity to a markdown file.
        
        Documents are stored in the documents/ directory with subdirectories
        by parent entity if applicable.
        """
        # Update timestamp
        doc.updated_at = datetime.now()
        
        # Build frontmatter and content
        fm = self._entity_to_frontmatter(doc)
        content = self._get_content(doc)
        
        # Create the markdown document
        post = frontmatter.Post(content, **fm)
        
        # Determine file path - documents go in documents/
        base_dir = self.data_dir / "documents"
        
        # If document has a parent entity, create a subdirectory
        if doc.parent_entity_id:
            parent_dir = base_dir / str(doc.parent_entity_id)[:8]
            parent_dir.mkdir(parents=True, exist_ok=True)
            directory = parent_dir
        else:
            directory = base_dir
        
        filename = f"{self._slugify(doc.title)}.md"
        filepath = directory / filename
        
        # Handle name collisions by appending ID
        if filepath.exists():
            existing_doc = self.read(filepath)
            if existing_doc and str(existing_doc["metadata"].get("id")) != str(doc.id):
                filename = f"{self._slugify(doc.title)}-{str(doc.id)[:8]}.md"
                filepath = directory / filename
        
        # Write the file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        logger.info(f"Wrote document '{doc.title}' to {filepath}")
        return filepath
    
    def read_document(self, doc_id: UUID | str) -> dict[str, Any] | None:
        """
        Read a document by its ID.
        
        Searches the documents/ directory tree.
        """
        id_str = str(doc_id)
        documents_dir = self.data_dir / "documents"
        
        if not documents_dir.exists():
            return None
        
        # Search all markdown files in documents/ and subdirectories
        for filepath in documents_dir.rglob("*.md"):
            doc = self.read(filepath)
            if doc and doc["metadata"].get("id") == id_str:
                return doc
        
        return None
    
    def list_entity_documents(self, entity_id: UUID | str) -> list[dict[str, Any]]:
        """
        List all documents attached to a specific entity.
        
        Returns documents where parent_entity_id matches the given entity.
        """
        id_str = str(entity_id)
        documents_dir = self.data_dir / "documents"
        results = []
        
        if not documents_dir.exists():
            return results
        
        # Search all documents
        for filepath in documents_dir.rglob("*.md"):
            doc = self.read(filepath)
            if doc and doc["metadata"].get("parent_entity_id") == id_str:
                results.append(doc)
        
        # Sort by document_type (general_info first) then by title
        def sort_key(d):
            doc_type = d["metadata"].get("document_type", "")
            is_general = doc_type == "general_info"
            title = d["metadata"].get("title", "")
            return (0 if is_general else 1, title)
        
        results.sort(key=sort_key)
        return results
    
    def get_general_info_document(self, entity_id: UUID | str) -> dict[str, Any] | None:
        """
        Get the General Info document for an entity.
        
        Returns None if no General Info document exists.
        """
        docs = self.list_entity_documents(entity_id)
        for doc in docs:
            if doc["metadata"].get("document_type") == "general_info":
                return doc
        return None
    
    def append_to_document(
        self, 
        doc_id: UUID | str, 
        content: str, 
        source: Source = Source.AGENT,
        section: str | None = None
    ) -> bool:
        """
        Append content to an existing document.
        
        Args:
            doc_id: Document ID
            content: Content to append (markdown)
            source: Who is appending (user/agent)
            section: Optional section header to add before content
        
        Returns True if successful.
        """
        doc = self.read_document(doc_id)
        if not doc:
            logger.warning(f"Cannot append to document {doc_id}: not found")
            return False
        
        # Check lock for user edits
        if doc["metadata"].get("locked") and source == Source.USER:
            logger.warning(f"Cannot append to locked document {doc_id}")
            return False
        
        # Build new content
        existing_content = doc["content"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if section:
            new_content = f"{existing_content}\n\n## {section}\n\n{content}\n\n_Added by {source.value} at {timestamp}_"
        else:
            new_content = f"{existing_content}\n\n{content}\n\n_Added by {source.value} at {timestamp}_"
        
        # Update frontmatter
        metadata = doc["metadata"]
        metadata["updated_at"] = datetime.now().isoformat()
        metadata["last_edited_by"] = source.value if hasattr(source, 'value') else source
        
        # Create and write updated document
        post = frontmatter.Post(new_content, **metadata)
        
        filepath = doc["path"]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        logger.info(f"Appended content to document {doc_id}")
        return True
    
    def update_document(
        self,
        doc_id: UUID | str,
        content: str | None = None,
        title: str | None = None,
        source: Source = Source.USER
    ) -> bool:
        """
        Update a document's content and/or title.
        
        Returns True if successful.
        """
        doc = self.read_document(doc_id)
        if not doc:
            logger.warning(f"Cannot update document {doc_id}: not found")
            return False
        
        # Check lock for user edits
        if doc["metadata"].get("locked") and source == Source.USER:
            logger.warning(f"Cannot update locked document {doc_id}")
            return False
        
        # Update fields
        metadata = doc["metadata"]
        metadata["updated_at"] = datetime.now().isoformat()
        metadata["last_edited_by"] = source.value if hasattr(source, 'value') else source
        
        if title is not None:
            metadata["title"] = title
        
        new_content = content if content is not None else doc["content"]
        
        # If title changed, update the content header
        if title is not None and new_content.startswith("#"):
            lines = new_content.split("\n")
            if lines[0].startswith("#"):
                lines[0] = f"# {title}"
                new_content = "\n".join(lines)
        
        # Create and write updated document
        post = frontmatter.Post(new_content, **metadata)
        
        filepath = doc["path"]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        
        logger.info(f"Updated document {doc_id}")
        return True
    
    def list_all_documents(self) -> list[dict[str, Any]]:
        """
        List all documents in the system.
        """
        documents_dir = self.data_dir / "documents"
        results = []
        
        if not documents_dir.exists():
            return results
        
        for filepath in documents_dir.rglob("*.md"):
            doc = self.read(filepath)
            if doc:
                results.append(doc)
        
        return results

