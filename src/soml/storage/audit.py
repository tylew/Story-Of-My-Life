"""
Audit Log - Track all changes for undo/correction support.

The audit log maintains a history of all document changes:
- Creates
- Updates (with before/after snapshots)
- Deletes (soft and hard)
- Corrections

This enables:
- Undo operations
- Change history review
- Correction propagation tracking
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from soml.core.config import settings, get_logger
from soml.storage.registry import RegistryStore

logger = get_logger("storage.audit")


AuditAction = Literal["create", "update", "delete", "restore", "correct", "merge"]


class AuditLog:
    """
    Audit log backed by SQLite.
    
    Works with the RegistryStore to maintain change history.
    """
    
    def __init__(self, registry: RegistryStore | None = None):
        """Initialize the audit log."""
        self.registry = registry or RegistryStore()
    
    def log(
        self,
        document_id: str | UUID,
        action: AuditAction,
        old_data: dict[str, Any] | str | None = None,
        new_data: dict[str, Any] | str | None = None,
        actor: str = "agent",
        item_type: str | None = None,
        item_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an audit entry.
        
        Args:
            document_id: The item being changed (entity/doc/relationship ID)
            action: The type of change
            old_data: Previous state (for updates/deletes)
            new_data: New state (for creates/updates)
            actor: Who made the change (user, agent, system)
            item_type: Type of item (entity, document, relationship)
            item_name: Human-readable name of the item
            metadata: Additional context
        """
        # Serialize data
        old_str = json.dumps(old_data) if isinstance(old_data, dict) else old_data
        new_str = json.dumps(new_data) if isinstance(new_data, dict) else new_data
        
        # Add metadata if provided
        if metadata:
            new_data_dict = json.loads(new_str) if new_str else {}
            new_data_dict["_audit_metadata"] = {
                "actor": actor,
                **metadata,
            }
            new_str = json.dumps(new_data_dict)
        
        self.registry.log_audit(
            doc_id=str(document_id),
            action=action,
            old_data=old_str,
            new_data=new_str,
            actor=actor,
            item_type=item_type,
            item_name=item_name,
        )
        
        logger.debug(f"Logged {action} for {item_type or 'item'} {document_id}")
    
    def log_create(
        self,
        document_id: str | UUID,
        data: dict[str, Any],
        actor: str = "agent",
        item_type: str | None = None,
        item_name: str | None = None,
    ) -> None:
        """Log an item creation."""
        self.log(document_id, "create", new_data=data, actor=actor, item_type=item_type, item_name=item_name)
    
    def log_update(
        self,
        document_id: str | UUID,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        actor: str = "agent",
        item_type: str | None = None,
        item_name: str | None = None,
    ) -> None:
        """Log an item update with before/after snapshots."""
        self.log(document_id, "update", old_data=old_data, new_data=new_data, actor=actor, item_type=item_type, item_name=item_name)
    
    def log_delete(
        self,
        document_id: str | UUID,
        data: dict[str, Any],
        soft: bool = True,
        actor: str = "agent",
        item_type: str | None = None,
        item_name: str | None = None,
    ) -> None:
        """Log an item deletion."""
        action = "delete"
        self.log(
            document_id,
            action,
            old_data=data,
            actor=actor,
            item_type=item_type,
            item_name=item_name,
            metadata={"soft_delete": soft},
        )
    
    def log_correction(
        self,
        document_id: str | UUID,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        correction_note: str,
        actor: str = "user",
        item_type: str | None = None,
        item_name: str | None = None,
    ) -> None:
        """Log a correction (always user-initiated)."""
        self.log(
            document_id,
            "correct",
            old_data=old_data,
            new_data=new_data,
            actor=actor,
            item_type=item_type,
            item_name=item_name,
            metadata={"correction_note": correction_note},
        )
    
    def log_merge(
        self,
        source_id: str | UUID,
        target_id: str | UUID,
        source_data: dict[str, Any],
        merged_data: dict[str, Any],
        actor: str = "user",
        item_name: str | None = None,
    ) -> None:
        """Log an entity merge (duplicate resolution)."""
        self.log(
            source_id,
            "merge",
            old_data=source_data,
            new_data={"merged_into": str(target_id), "merged_data": merged_data},
            actor=actor,
            item_type="entity",
            item_name=item_name,
        )
    
    def get_history(
        self,
        document_id: str | UUID,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get the change history for a document."""
        entries = self.registry.get_audit_history(str(document_id), limit)
        
        # Parse JSON data
        result = []
        for entry in entries:
            parsed = dict(entry)
            if parsed.get("old_data"):
                try:
                    parsed["old_data"] = json.loads(parsed["old_data"])
                except json.JSONDecodeError:
                    pass
            if parsed.get("new_data"):
                try:
                    parsed["new_data"] = json.loads(parsed["new_data"])
                except json.JSONDecodeError:
                    pass
            result.append(parsed)
        
        return result
    
    def get_last_state(self, document_id: str | UUID) -> dict[str, Any] | None:
        """Get the last known state of a document (for undo)."""
        history = self.get_history(document_id, limit=1)
        if history:
            entry = history[0]
            if entry["action"] in ("update", "correct"):
                return entry.get("old_data")
            elif entry["action"] == "delete":
                return entry.get("old_data")
        return None
    
    def can_undo(self, document_id: str | UUID) -> bool:
        """Check if the last action on a document can be undone."""
        history = self.get_history(document_id, limit=1)
        if not history:
            return False
        
        action = history[0]["action"]
        return action in ("update", "delete", "correct")
    
    def get_corrections(self, document_id: str | UUID) -> list[dict[str, Any]]:
        """Get all corrections made to a document."""
        history = self.get_history(document_id, limit=1000)
        return [e for e in history if e["action"] == "correct"]
    
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
        entries = self.registry.get_recent_activity(
            limit=limit, item_type=item_type, actor=actor, since=since
        )
        
        result = []
        for entry in entries:
            parsed = dict(entry)
            if parsed.get("old_data"):
                try:
                    parsed["old_data"] = json.loads(parsed["old_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if parsed.get("new_data"):
                try:
                    parsed["new_data"] = json.loads(parsed["new_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(parsed)
        
        return result
    
    def get_entity_activity(self, entity_id: str | UUID, limit: int = 50) -> list[dict[str, Any]]:
        """Get all activity related to an entity, including its documents."""
        entries = self.registry.get_entity_activity(str(entity_id), limit=limit)
        
        result = []
        for entry in entries:
            parsed = dict(entry)
            if parsed.get("old_data"):
                try:
                    parsed["old_data"] = json.loads(parsed["old_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if parsed.get("new_data"):
                try:
                    parsed["new_data"] = json.loads(parsed["new_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(parsed)
        
        return result

