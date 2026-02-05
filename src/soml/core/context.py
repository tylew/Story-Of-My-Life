"""
SwarmContext - Shared state passed between agents in the swarm.

This context accumulates data as it flows through the ingestion pipeline
and provides access to shared resources for all agents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from soml.core.types import (
    ClassifiedIntent,
    Entity,
    EntityProposal,
    ExtractedEntity,
    ExtractedTimestamp,
    Relationship,
    RelationshipProposal,
)


@dataclass
class SwarmContext:
    """
    Shared context passed between agents in the swarm.
    
    This context is:
    - Created at the start of each request
    - Accumulated as data flows through the pipeline
    - Passed via handoffs between agents
    - Used to track pending proposals and actions
    """
    
    # ==========================================
    # Session Information
    # ==========================================
    session_id: UUID = field(default_factory=uuid4)
    """Unique ID for this session/request."""
    
    user_id: str = "default"
    """User identifier (for multi-user setups)."""
    
    current_date: datetime = field(default_factory=datetime.now)
    """Current date for resolving relative times."""
    
    # ==========================================
    # Input Data
    # ==========================================
    raw_input: str = ""
    """The original user input."""
    
    input_type: str = "text"
    """Type of input (text, query, correction, etc.)."""
    
    # ==========================================
    # Document Being Processed
    # ==========================================
    document_id: UUID | None = None
    """UUID of document being created/updated."""
    
    document_path: Path | None = None
    """Filesystem path to the document."""
    
    document_checksum: str | None = None
    """Content hash for change detection."""
    
    # ==========================================
    # Extracted Data (Accumulated Through Pipeline)
    # ==========================================
    timestamps: list[ExtractedTimestamp] = field(default_factory=list)
    """Timestamps extracted by Time Extractor."""
    
    entities: list[ExtractedEntity] = field(default_factory=list)
    """Entities extracted by Entity Extractor."""
    
    intent: ClassifiedIntent | None = None
    """Intent classification result."""
    
    relationships: list[Relationship] = field(default_factory=list)
    """Relationships proposed by Relationship Proposer."""
    
    # ==========================================
    # Created/Updated Entities
    # ==========================================
    created_entities: list[Entity] = field(default_factory=list)
    """Entities created during this session."""
    
    updated_entities: list[Entity] = field(default_factory=list)
    """Entities updated during this session."""
    
    # ==========================================
    # Proposals (Need User Confirmation)
    # ==========================================
    entity_proposals: list[EntityProposal] = field(default_factory=list)
    """Entity proposals awaiting user confirmation."""
    
    relationship_proposals: list[RelationshipProposal] = field(default_factory=list)
    """Relationship proposals awaiting user confirmation."""
    
    # ==========================================
    # Agent Configuration (legacy - not actively used)
    # ==========================================
    
    # ==========================================
    # Execution Tracking
    # ==========================================
    agent_trace: list[str] = field(default_factory=list)
    """List of agents that have processed this context."""
    
    errors: list[dict[str, Any]] = field(default_factory=list)
    """Errors encountered during processing."""
    
    # ==========================================
    # Methods
    # ==========================================
    
    def add_timestamp(self, timestamp: ExtractedTimestamp) -> None:
        """Add an extracted timestamp."""
        self.timestamps.append(timestamp)
    
    def add_entity(self, entity: ExtractedEntity) -> None:
        """Add an extracted entity."""
        self.entities.append(entity)
    
    def add_relationship(self, relationship: Relationship) -> None:
        """Add a proposed relationship."""
        self.relationships.append(relationship)
    
    def add_entity_proposal(self, proposal: EntityProposal) -> None:
        """Add an entity proposal for user confirmation."""
        self.entity_proposals.append(proposal)
    
    def add_relationship_proposal(self, proposal: RelationshipProposal) -> None:
        """Add a relationship proposal for user confirmation."""
        self.relationship_proposals.append(proposal)
    
    def record_agent(self, agent_name: str) -> None:
        """Record that an agent processed this context."""
        self.agent_trace.append(f"{agent_name}@{datetime.now().isoformat()}")
    
    def record_error(self, agent: str, error: str, details: dict | None = None) -> None:
        """Record an error during processing."""
        self.errors.append({
            "agent": agent,
            "error": error,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_primary_timestamp(self) -> datetime | None:
        """Get the primary timestamp (highest confidence)."""
        if not self.timestamps:
            return None
        return max(self.timestamps, key=lambda t: t.confidence).resolved
    
    def get_entities_by_type(self, entity_type: str) -> list[ExtractedEntity]:
        """Get entities of a specific type."""
        return [e for e in self.entities if e.entity_type.value == entity_type]
    
    def has_pending_proposals(self) -> bool:
        """Check if there are pending proposals."""
        return bool(self.entity_proposals or self.relationship_proposals)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "session_id": str(self.session_id),
            "user_id": self.user_id,
            "current_date": self.current_date.isoformat(),
            "raw_input": self.raw_input,
            "input_type": self.input_type,
            "document_id": str(self.document_id) if self.document_id else None,
            "timestamps": [
                {"text": t.original_text, "resolved": t.resolved.isoformat(), "confidence": t.confidence}
                for t in self.timestamps
            ],
            "entities": [
                {"name": e.name, "type": e.entity_type.value, "confidence": e.confidence}
                for e in self.entities
            ],
            "relationships": [
                {"source": str(r.source_id), "target": str(r.target_id), "type": r.relationship_type}
                for r in self.relationships
            ],
            "agent_trace": self.agent_trace,
            "errors": self.errors,
        }


def create_context(
    raw_input: str,
    input_type: str = "text",
    user_id: str = "default",
) -> SwarmContext:
    """Factory function to create a new SwarmContext."""
    return SwarmContext(
        raw_input=raw_input,
        input_type=input_type,
        user_id=user_id,
        current_date=datetime.now(),
    )

