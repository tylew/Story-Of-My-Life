"""
Core type definitions for Story of My Life.

These types represent the core ontology:
- Note, Event, Person, Relationship, Goal, Project, Memory, Period
"""

from datetime import datetime, date, time
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


# ============================================
# Enums
# ============================================

class EntityType(str, Enum):
    """Types of entities in the system."""
    PERSON = "person"
    PROJECT = "project"
    GOAL = "goal"
    EVENT = "event"
    NOTE = "note"
    MEMORY = "memory"
    DOCUMENT = "document"
    PERIOD = "period"


class TemporalState(str, Enum):
    """Temporal state of an event or note."""
    OBSERVED = "observed"      # Actually happened
    PLANNED = "planned"        # Scheduled to happen
    CANCELLED = "cancelled"    # Was planned, won't happen
    REVISED = "revised"        # Happened differently than recorded
    UNCERTAIN = "uncertain"    # May or may not have happened


class RelationshipCategory(str, Enum):
    """Categories of relationships."""
    PERSONAL = "personal"      # Human-to-human relationships
    STRUCTURAL = "structural"  # Entity-to-entity structural relationships


class PersonalRelationshipType(str, Enum):
    """Types of personal (human-to-human) relationships."""
    FRIEND = "friend"
    FAMILY = "family"
    PARTNER = "partner"
    # Employment-based relationships (current)
    WORKS_WITH = "works_with"       # Currently work together
    COWORKER = "coworker"           # Alias for works_with
    # Employment-based relationships (past)
    WORKED_WITH = "worked_with"     # Previously worked together
    FORMER_COWORKER = "former_coworker"  # Alias for worked_with
    # Mentorship
    MENTOR = "mentor"
    MENTEE = "mentee"
    # Other
    ACQUAINTANCE = "acquaintance"
    PROFESSIONAL = "professional"
    OTHER = "other"


class StructuralRelationshipType(str, Enum):
    """Types of structural relationships between entities."""
    PART_OF = "part_of"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    RELATED_TO = "related_to"
    REFERENCES = "references"
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"
    STAKEHOLDER_OF = "stakeholder_of"
    # Multi-day event relationships
    NEXT_DAY = "next_day"           # day 1 -> day 2 sequence for multi-day events
    PART_OF_EVENT = "part_of_event" # day event -> parent multi-day event
    # Period relationships
    DURING = "during"               # event/entity occurred during a Period


# Union type for all relationship types
RelationshipType = PersonalRelationshipType | StructuralRelationshipType


class Source(str, Enum):
    """Source of entity creation."""
    USER = "user"          # Explicitly created by user
    AGENT = "agent"        # Inferred/created by agent
    IMPORT = "import"      # Imported from external source


class OpenLoopType(str, Enum):
    """Types of open loops detected by the system."""
    RELATIONSHIP = "relationship"  # Quiet relationship
    PROJECT = "project"            # Stalled project
    GOAL = "goal"                  # Stalled goal
    COMMITMENT = "commitment"      # Unfulfilled commitment
    QUESTION = "question"          # Unanswered question
    NEEDS_REVIEW = "needs_review"  # Entity/doc flagged for user review


class DocumentType(str, Enum):
    """Types of documents that can be attached to entities."""
    GENERAL_INFO = "general_info"  # LLM-only, one per entity - locked
    NOTE = "note"                  # User/LLM created notes
    MEETING = "meeting"            # Meeting notes
    RESEARCH = "research"          # Research documents
    PLAN = "plan"                  # Plans/roadmaps
    CUSTOM = "custom"              # Any other document type


class ClarificationPriority(str, Enum):
    """Priority level for clarifying questions in multi-turn conversations."""
    REQUIRED = "required"    # Must answer; can abort if not answered
    OPTIONAL = "optional"    # Nice to have; can skip and proceed


class ConversationState(str, Enum):
    """State of a multi-turn conversation."""
    ANALYZING = "analyzing"               # Processing user input
    NEEDS_CLARIFICATION = "needs_clarification"  # Waiting for user to answer questions
    READY_TO_PROPOSE = "ready_to_propose"   # All info gathered, ready to propose
    PENDING_CONFIRMATION = "pending_confirmation"  # Proposals shown, awaiting user confirmation
    EXECUTED = "executed"                  # Proposals executed successfully
    ABORTED = "aborted"                    # User cancelled or required clarification not provided


# ============================================
# Base Models
# ============================================

class BaseEntity(BaseModel):
    """Base class for all entities."""
    
    id: UUID = Field(default_factory=uuid4)
    """Unique identifier for the entity."""
    
    created_at: datetime = Field(default_factory=datetime.now)
    """When the entity was created."""
    
    updated_at: datetime = Field(default_factory=datetime.now)
    """When the entity was last updated."""
    
    source: Source = Source.AGENT
    """How this entity was created."""
    
    needs_review: bool = False
    """Flag for items requiring user attention. Surfaced as open loop."""
    
    review_reason: str | None = None
    """Why this entity needs review (set by agent)."""
    
    tags: list[str] = Field(default_factory=list)
    """Topic tags for categorization."""
    
    links: list[UUID] = Field(default_factory=list)
    """Related document IDs (for wikilinks)."""
    
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    """Flexible key-value storage for user/LLM-defined properties."""
    
    class Config:
        use_enum_values = True


# ============================================
# Core Entities
# ============================================

class EmploymentRecord(BaseModel):
    """A record of employment at an organization."""
    
    organization: str
    """Name of the company/organization."""
    
    role: str | None = None
    """Job title or role."""
    
    start_date: date | None = None
    """When they started (if known)."""
    
    end_date: date | None = None
    """When they left (None = currently employed)."""
    
    is_current: bool = True
    """Whether this is their current employment."""


class Person(BaseEntity):
    """A person in the user's life."""
    
    entity_type: Literal["person"] = "person"
    
    name: str
    """Person's name."""
    
    disambiguator: str | None = None
    """One-liner context for disambiguation, e.g., 'Cayden from Atitan board'."""
    
    email: str | None = None
    phone: str | None = None
    
    # Employment tracking
    current_employer: str | None = None
    """Current employer name (shortcut for quick access)."""
    
    employment_history: list[EmploymentRecord] = Field(default_factory=list)
    """Full employment history with dates."""
    
    last_interaction: datetime | None = None
    """When user last interacted with this person."""
    
    def add_employment(self, org: str, role: str | None = None, start_date: date | None = None) -> None:
        """Add current employment, marking previous as ended."""
        # End any current employment
        for emp in self.employment_history:
            if emp.is_current:
                emp.is_current = False
                emp.end_date = emp.end_date or date.today()
        
        # Add new employment
        self.employment_history.append(EmploymentRecord(
            organization=org,
            role=role,
            start_date=start_date,
            is_current=True,
        ))
        self.current_employer = org
    
    def end_employment(self, end_date: date | None = None) -> None:
        """End current employment."""
        for emp in self.employment_history:
            if emp.is_current:
                emp.is_current = False
                emp.end_date = end_date or date.today()
        self.current_employer = None


class Project(BaseEntity):
    """A multi-stakeholder effort with defined outcomes."""
    
    entity_type: Literal["project"] = "project"
    
    name: str
    """Project name."""
    
    status: Literal["active", "completed", "on_hold", "cancelled"] = "active"
    
    stakeholders: list[UUID] = Field(default_factory=list)
    """UUIDs of people involved in this project."""
    
    goals: list[UUID] = Field(default_factory=list)
    """UUIDs of goals that are part of this project."""
    
    start_date: datetime | None = None
    end_date: datetime | None = None
    
    last_activity: datetime | None = None
    """When the project last had activity."""
    
    children: list[UUID] = Field(default_factory=list)
    """Child document IDs for hierarchical projects."""


class Goal(BaseEntity):
    """A personal desired outcome."""
    
    entity_type: Literal["goal"] = "goal"
    
    title: str
    """Goal title."""
    
    status: Literal["active", "completed", "abandoned"] = "active"
    
    target_date: datetime | None = None
    """When the goal should be achieved."""
    
    progress: int = Field(default=0, ge=0, le=100)
    """Progress percentage (0-100)."""
    
    parent_project: UUID | None = None
    """If this goal is part of a project."""
    
    last_progress: datetime | None = None
    """When progress was last made."""


class Event(BaseEntity):
    """A specific occurrence on a date.
    
    Events have a specific on_date (required) and optional start/end times.
    Multi-day events are split into separate day-events linked with 
    PART_OF_EVENT and NEXT_DAY relationships.
    """
    
    entity_type: Literal["event"] = "event"
    
    title: str
    """Event title."""
    
    temporal_state: TemporalState = TemporalState.OBSERVED
    """Whether this event happened, is planned, etc."""
    
    # Date and time fields
    on_date: date | None = None
    """The specific date this event occurs (required for complete event)."""
    
    start_time: time | None = None
    """Optional start time of day."""
    
    end_time: time | None = None
    """Optional end time of day."""
    
    # Multi-day event support
    parent_event_id: UUID | None = None
    """If this is a day-event, reference to the parent multi-day event."""
    
    day_number: int | None = None
    """For multi-day events, which day this is (1, 2, 3...)."""
    
    total_days: int | None = None
    """Total number of days in the parent multi-day event."""
    
    # Location and participants
    location: str | None = None
    
    participants: list[UUID] = Field(default_factory=list)
    """UUIDs of people who participated."""
    
    related_projects: list[UUID] = Field(default_factory=list)
    """UUIDs of related projects."""
    
    @computed_field
    @property
    def is_multi_day_child(self) -> bool:
        """Whether this is a child event of a multi-day event."""
        return self.parent_event_id is not None


class Note(BaseEntity):
    """A piece of captured information."""
    
    entity_type: Literal["note"] = "note"
    
    title: str | None = None
    """Optional title."""
    
    content: str
    """The note content."""
    
    temporal_state: TemporalState = TemporalState.OBSERVED
    
    captured_at: datetime = Field(default_factory=datetime.now)
    """When the note was captured."""
    
    referenced_time: datetime | None = None
    """Time the note refers to (if different from captured_at)."""
    
    emotional_tone: float = Field(default=0.0, ge=-1.0, le=1.0)
    """Emotional tone: -1.0 (negative) to +1.0 (positive)."""
    
    urgency: int = Field(default=0, ge=0, le=100)
    """Urgency level (0-100)."""


class Memory(BaseEntity):
    """A synthesized summary of related notes/events."""
    
    entity_type: Literal["memory"] = "memory"
    
    title: str
    """Memory title."""
    
    summary: str
    """Synthesized summary."""
    
    time_period_start: datetime | None = None
    time_period_end: datetime | None = None
    
    source_documents: list[UUID] = Field(default_factory=list)
    """UUIDs of source notes/events."""
    
    themes: list[str] = Field(default_factory=list)
    """Key themes identified."""


class Period(BaseEntity):
    """A span of time (life phase, project timeframe, relationship period).
    
    Periods represent meaningful time spans in a person's life, such as:
    - Life phases ("College years", "Time at Company X")
    - Project timeframes ("Q1 2026 sprint", "Summer vacation")
    - Relationship periods ("Dating Sarah", "Working with John")
    
    A Period is considered incomplete until both start_date and end_date are set.
    The LLM should distinguish between:
    - Events: Specific occurrences ("meeting tomorrow", "birthday party on June 5")
    - Periods: Time spans ("during college", "while at Google", "Q1 planning phase")
    """
    
    entity_type: Literal["period"] = "period"
    
    name: str
    """Period name (e.g., 'College years', 'Q1 2026 sprint')."""
    
    start_date: date | None = None
    """Start date of the period. Period is incomplete until this is set."""
    
    end_date: date | None = None
    """End date of the period. Period is incomplete until this is set."""
    
    # Optional: Track associated entities during this period
    related_people: list[UUID] = Field(default_factory=list)
    """People relevant to this period."""
    
    related_projects: list[UUID] = Field(default_factory=list)
    """Projects during this period."""
    
    @computed_field
    @property
    def is_complete(self) -> bool:
        """Whether this period has both start and end dates."""
        return self.start_date is not None and self.end_date is not None


class Document(BaseEntity):
    """A document attached to an entity.
    
    Documents are the primary way to store detailed information about entities.
    Each entity has one locked General Info document (LLM-only editable) plus
    any number of user-created documents.
    """
    
    entity_type: Literal["document"] = "document"
    
    title: str
    """Document title."""
    
    document_type: DocumentType = DocumentType.CUSTOM
    """Type of document (general_info, note, meeting, etc.)."""
    
    content: str = ""
    """Markdown content of the document."""
    
    parent_entity_id: UUID | None = None
    """The entity this document belongs to."""
    
    parent_entity_type: EntityType | None = None
    """Type of the parent entity."""
    
    locked: bool = False
    """If True, only LLM can edit this document (for General Info docs)."""
    
    last_edited_by: Source = Source.USER
    """Who last edited this document."""


# ============================================
# Relationships
# ============================================

class Relationship(BaseModel):
    """A relationship between two entities."""
    
    id: UUID = Field(default_factory=uuid4)
    
    source_id: UUID
    """Source entity UUID."""
    
    target_id: UUID
    """Target entity UUID."""
    
    category: RelationshipCategory
    """Personal or structural."""
    
    relationship_type: str
    """Specific relationship type (friend, depends_on, etc.)."""
    
    strength: float = Field(default=0.5, ge=0.0, le=1.0)
    """Relationship strength (0.0-1.0)."""
    
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    """Emotional sentiment: -1.0 (negative) to +1.0 (positive)."""
    
    last_interaction: datetime | None = None
    """Last interaction for this relationship."""
    
    notes: str | None = None
    """Notes about this relationship."""
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ============================================
# Open Loops
# ============================================

class OpenLoop(BaseModel):
    """An open loop detected by the system."""
    
    id: UUID = Field(default_factory=uuid4)
    
    loop_type: OpenLoopType
    """Type of open loop."""
    
    entity_id: UUID
    """The entity this loop relates to."""
    
    entity_type: EntityType
    """Type of the related entity."""
    
    urgency: int = Field(default=50, ge=0, le=100)
    """Urgency level (0-100)."""
    
    suggested_timing: datetime | None = None
    """When to check in about this."""
    
    prompt: str
    """Natural language prompt for the check-in."""
    
    detected_at: datetime = Field(default_factory=datetime.now)
    """When this loop was detected."""
    
    resolved_at: datetime | None = None
    """When/if this loop was resolved."""


# ============================================
# Proposals
# ============================================

class EntityProposal(BaseModel):
    """A proposal for the user to confirm/reject an entity."""
    
    id: UUID = Field(default_factory=uuid4)
    
    action: Literal["create", "merge", "update", "delete"]
    """What action is being proposed."""
    
    entity_type: EntityType
    """Type of entity."""
    
    entity_data: dict
    """The proposed entity data."""
    
    reason: str
    """Natural language explanation."""
    
    source_text: str | None = None
    """The text that triggered this proposal."""
    
    created_at: datetime = Field(default_factory=datetime.now)


class RelationshipProposal(BaseModel):
    """A proposal for a new relationship."""
    
    id: UUID = Field(default_factory=uuid4)
    
    source_id: UUID
    target_id: UUID
    
    proposed_type: str
    """Proposed relationship type."""
    
    category: RelationshipCategory
    
    reason: str
    """Natural language explanation."""
    
    source_text: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================
# Extracted Data (from ingestion pipeline)
# ============================================

class ExtractedTimestamp(BaseModel):
    """A timestamp extracted from text."""
    
    original_text: str
    """The original text that was parsed."""
    
    resolved: datetime
    """The resolved datetime."""
    
    is_relative: bool = False
    """Whether this was a relative reference (yesterday, last week)."""
    
    confidence: float = 1.0


class ExtractedEntity(BaseModel):
    """An entity extracted from text."""
    
    name: str
    entity_type: EntityType
    context: str | None = None
    """Context clues for disambiguation."""
    
    confidence: float = 0.8


class ClassifiedIntent(BaseModel):
    """Classified intent from text."""
    
    document_type: EntityType
    temporal_state: TemporalState
    emotional_tone: float = 0.0
    urgency: int = 0


# ============================================
# Multi-Turn Conversation Types
# ============================================

class Clarification(BaseModel):
    """A clarifying question in a multi-turn conversation."""
    
    id: str
    """Unique identifier for this clarification."""
    
    question: str
    """The question to ask the user."""
    
    priority: ClarificationPriority
    """Whether this is required or optional."""
    
    options: list[str] | None = None
    """For multiple choice questions, the available options."""
    
    context: str | None = None
    """Why we're asking this question (shown to user)."""
    
    default_value: str | None = None
    """Default value for optional clarifications."""
    
    answer: str | None = None
    """The user's answer (filled in after user responds)."""
    
    skipped: bool = False
    """Whether the user skipped this optional clarification."""


class ClarificationRequest(BaseModel):
    """A request for clarifications from the system to the user."""
    
    conversation_id: str
    """The conversation this belongs to."""
    
    state: ConversationState = ConversationState.NEEDS_CLARIFICATION
    """Current state of the conversation."""
    
    clarifications: list[Clarification]
    """The questions to ask."""
    
    partial_extraction: dict | None = None
    """The extraction so far (stored for when user responds)."""
    
    message: str | None = None
    """Optional message to show with the clarifications."""


class ClarificationResponse(BaseModel):
    """User's response to clarification questions."""
    
    conversation_id: str
    """The conversation this belongs to."""
    
    answers: dict[str, str | None]
    """Map of clarification_id -> answer (None means skipped)."""


# Type alias for any entity
Entity = Person | Project | Goal | Event | Note | Memory | Period | Document

