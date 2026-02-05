"""
MCP Tools - Entity upsert tools.

Smart upsert operations for all entity types:
- Person
- Project
- Goal
- Event
- Period
"""

from datetime import datetime, date
from uuid import UUID, uuid4

from soml.core.types import (
    EntityType,
    Event,
    Goal,
    Period,
    Person,
    Project,
    Source,
    TemporalState,
)
from soml.mcp.tools.base import (
    UpsertResult,
    _get_graph_store,
    _get_md_store,
    _get_registry,
    _get_resolver,
    _create_general_info_document,
    _append_to_general_info,
    _queue_embedding_generation,
    logger,
)


# ============================================
# Person Upsert
# ============================================

def upsert_person(
    name: str,
    context: str | None = None,
    data: dict | None = None,
    conversation_id: str | None = None,
) -> UpsertResult:
    """
    Create or update a person entity.
    
    Internally:
    1. Normalizes name and searches for matches
    2. If exact match: updates with new data
    3. If ambiguous: returns candidates for confirmation
    4. If new: creates person
    
    Args:
        name: Person's name
        context: Disambiguating context (e.g., "user's father")
        data: Additional data fields (email, phone, notes, etc.)
        conversation_id: Conversation ID for context-based resolution
    
    Returns:
        UpsertResult with action taken
    """
    resolver = _get_resolver()
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    data = data or {}
    
    # Get conversation context if available
    conv_entities = None
    if conversation_id:
        from soml.storage.conversations import ConversationStore
        conv_store = ConversationStore()
        conv_entities = conv_store.get_entity_context(conversation_id)
    
    # Resolve the entity
    result = resolver.resolve(
        name=name,
        entity_type=EntityType.PERSON,
        context=context,
        conversation_entities=conv_entities,
    )
    
    if result.needs_confirmation:
        return UpsertResult(
            action="needs_confirmation",
            entity_id=None,
            entity={"name": name, "context": context, **data},
            candidates=result.candidates,
        )
    
    if result.found:
        # Update existing
        entity_id = result.entity_id
        existing = registry.get(entity_id)
        
        if not existing:
            # Shouldn't happen, but handle gracefully
            return _create_person(name, context, data, md_store, registry, graph_store)
        
        # Merge new data
        changes = []
        md_doc = md_store.read_by_id(entity_id, EntityType.PERSON)
        
        if md_doc:
            metadata = md_doc.get("metadata", {})
            
            # Update fields if new data provided
            if context and not metadata.get("disambiguator"):
                metadata["disambiguator"] = context
                changes.append(f"Added disambiguator: {context}")
            
            if data.get("email") and not metadata.get("email"):
                metadata["email"] = data["email"]
                changes.append(f"Added email")
            
            if data.get("phone") and not metadata.get("phone"):
                metadata["phone"] = data["phone"]
                changes.append(f"Added phone")
            
            # Handle custom_fields merge
            if data.get("custom_fields"):
                existing_custom = metadata.get("custom_fields", {})
                existing_custom.update(data["custom_fields"])
                metadata["custom_fields"] = existing_custom
                changes.append("Updated custom_fields")
            
            # Handle context/notes - append to General Info document
            if data.get("notes") or data.get("context"):
                content_to_add = data.get("notes") or data.get("context")
                _append_to_general_info(
                    entity_id=entity_id,
                    entity_type=EntityType.PERSON,
                    entity_name=metadata.get("name", name),
                    content=content_to_add,
                    md_store=md_store,
                    registry=registry,
                )
                changes.append("Appended to General Info document")
            
            if changes:
                # Create updated Person and write
                person = Person(
                    id=UUID(entity_id),
                    name=metadata.get("name", name),
                    disambiguator=metadata.get("disambiguator"),
                    email=metadata.get("email"),
                    phone=metadata.get("phone"),
                    custom_fields=metadata.get("custom_fields", {}),
                    created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
                    source=Source(metadata.get("source", "agent")),
                )
                
                filepath = md_store.write(person)
                
                # Update registry
                registry.index(
                    doc_id=entity_id,
                    path=filepath,
                    entity_type=EntityType.PERSON,
                    name=person.name,
                    checksum=md_store._compute_checksum(md_doc["content"]),
                    content=md_doc["content"],
                )
                
                # Update graph
                graph_store.upsert_node(person)
                
                return UpsertResult(
                    action="updated",
                    entity_id=entity_id,
                    entity=metadata,
                    changes=changes,
                )
        
        # No changes needed
        return UpsertResult(
            action="no_change",
            entity_id=entity_id,
            entity=existing,
        )
    
    # Create new
    return _create_person(name, context, data, md_store, registry, graph_store)


def _create_person(
    name: str,
    context: str | None,
    data: dict,
    md_store,
    registry,
    graph_store,
) -> UpsertResult:
    """Create a new person entity and auto-create General Info document."""
    # Extract custom_fields from data
    custom_fields = data.pop("custom_fields", {}) or {}
    
    person = Person(
        id=uuid4(),
        name=name,
        disambiguator=context or data.get("disambiguator"),
        email=data.get("email"),
        phone=data.get("phone"),
        custom_fields=custom_fields,
        source=Source.AGENT,
    )
    
    # Write to markdown
    filepath = md_store.write(person)
    
    # Index in registry (entity file is now metadata-only, no content body)
    registry.index(
        doc_id=str(person.id),
        path=filepath,
        entity_type=EntityType.PERSON,
        name=person.name,
        checksum=md_store._compute_checksum(f"# {person.name}"),
        content=f"# {person.name}",
    )
    
    # Add to graph
    graph_store.upsert_node(person)
    
    # Auto-create General Info document (always created, even with placeholder)
    initial_context = context or data.get("context") or f"Information about {person.name}."
    _create_general_info_document(
        entity_id=str(person.id),
        entity_type=EntityType.PERSON,
        entity_name=person.name,
        initial_content=initial_context,
        md_store=md_store,
        registry=registry,
    )
    
    # Generate embedding for semantic search (async, non-blocking)
    _queue_embedding_generation(str(person.id))
    
    logger.info(f"Created person: {person.name} ({person.id})")
    
    return UpsertResult(
        action="created",
        entity_id=str(person.id),
        entity={
            "id": str(person.id),
            "name": person.name,
            "type": "person",
            "disambiguator": person.disambiguator,
        },
    )


# ============================================
# Project Upsert
# ============================================

def upsert_project(
    name: str,
    context: str | None = None,
    data: dict | None = None,
    conversation_id: str | None = None,
) -> UpsertResult:
    """
    Create or update a project entity.
    
    Args:
        name: Project name
        context: Disambiguating context
        data: Additional fields (description, status, stakeholders, etc.)
        conversation_id: Conversation ID for context-based resolution
    """
    resolver = _get_resolver()
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    data = data or {}
    
    # Resolve
    result = resolver.resolve(
        name=name,
        entity_type=EntityType.PROJECT,
        context=context,
    )
    
    if result.needs_confirmation:
        return UpsertResult(
            action="needs_confirmation",
            entity_id=None,
            entity={"name": name, "context": context, **data},
            candidates=result.candidates,
        )
    
    if result.found:
        # Update existing
        entity_id = result.entity_id
        existing = registry.get(entity_id)
        
        # TODO: Merge data like we do for person
        return UpsertResult(
            action="no_change",
            entity_id=entity_id,
            entity=existing,
        )
    
    # Create new
    custom_fields = data.pop("custom_fields", {}) or {}
    
    project = Project(
        id=uuid4(),
        name=name,
        status=data.get("status", "active"),
        custom_fields=custom_fields,
        source=Source.AGENT,
    )
    
    filepath = md_store.write(project)
    
    registry.index(
        doc_id=str(project.id),
        path=filepath,
        entity_type=EntityType.PROJECT,
        name=project.name,
        checksum=md_store._compute_checksum(f"# {project.name}"),
        content=f"# {project.name}",
    )
    
    graph_store.upsert_node(project)
    
    # Auto-create General Info document (always created, even with placeholder)
    initial_context = context or data.get("context") or f"Information about {project.name}."
    _create_general_info_document(
        entity_id=str(project.id),
        entity_type=EntityType.PROJECT,
        entity_name=project.name,
        initial_content=initial_context,
        md_store=md_store,
        registry=registry,
    )
    
    # Generate embedding for semantic search
    _queue_embedding_generation(str(project.id))
    
    logger.info(f"Created project: {project.name} ({project.id})")
    
    return UpsertResult(
        action="created",
        entity_id=str(project.id),
        entity={
            "id": str(project.id),
            "name": project.name,
            "type": "project",
        },
    )


# ============================================
# Goal Upsert
# ============================================

def upsert_goal(
    title: str,
    context: str | None = None,
    data: dict | None = None,
    conversation_id: str | None = None,
) -> UpsertResult:
    """
    Create or update a goal entity.
    
    Args:
        title: Goal title
        context: Additional context
        data: Additional fields (description, target_date, progress, etc.)
        conversation_id: Conversation ID for context-based resolution
    """
    resolver = _get_resolver()
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    data = data or {}
    
    # Resolve using title as name
    result = resolver.resolve(
        name=title,
        entity_type=EntityType.GOAL,
        context=context,
    )
    
    if result.needs_confirmation:
        return UpsertResult(
            action="needs_confirmation",
            entity_id=None,
            entity={"title": title, "context": context, **data},
            candidates=result.candidates,
        )
    
    if result.found:
        return UpsertResult(
            action="no_change",
            entity_id=result.entity_id,
            entity=registry.get(result.entity_id),
        )
    
    # Create new
    custom_fields = data.pop("custom_fields", {}) or {}
    
    goal = Goal(
        id=uuid4(),
        title=title,
        status=data.get("status", "active"),
        target_date=data.get("target_date"),
        progress=data.get("progress", 0),
        custom_fields=custom_fields,
        source=Source.AGENT,
    )
    
    filepath = md_store.write(goal)
    
    registry.index(
        doc_id=str(goal.id),
        path=filepath,
        entity_type=EntityType.GOAL,
        name=goal.title,
        checksum=md_store._compute_checksum(f"# {goal.title}"),
        content=f"# {goal.title}",
    )
    
    graph_store.upsert_node(goal)
    
    # Auto-create General Info document (always created, even with placeholder)
    initial_context = context or data.get("context") or f"Information about {goal.title}."
    _create_general_info_document(
        entity_id=str(goal.id),
        entity_type=EntityType.GOAL,
        entity_name=goal.title,
        initial_content=initial_context,
        md_store=md_store,
        registry=registry,
    )
    
    # Generate embedding for semantic search
    _queue_embedding_generation(str(goal.id))
    
    logger.info(f"Created goal: {goal.title} ({goal.id})")
    
    return UpsertResult(
        action="created",
        entity_id=str(goal.id),
        entity={
            "id": str(goal.id),
            "title": goal.title,
            "type": "goal",
        },
    )


# ============================================
# Event Upsert
# ============================================

def upsert_event(
    title: str,
    on_date: date | str | None = None,
    context: str | None = None,
    data: dict | None = None,
    conversation_id: str | None = None,
) -> UpsertResult:
    """
    Create or update an event entity.
    
    Args:
        title: Event title
        on_date: Date of the event
        context: Additional context
        data: Additional fields (description, location, participants, etc.)
        conversation_id: Conversation ID for context-based resolution
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    data = data or {}
    
    # Parse date if string
    if isinstance(on_date, str):
        try:
            on_date = date.fromisoformat(on_date)
        except ValueError:
            import dateparser
            parsed = dateparser.parse(on_date)
            on_date = parsed.date() if parsed else None
    
    # Events are more unique - don't do fuzzy matching
    # Just check for exact title + date match
    
    # Create new event
    custom_fields = data.pop("custom_fields", {}) or {}
    
    event = Event(
        id=uuid4(),
        title=title,
        on_date=on_date,
        location=data.get("location"),
        temporal_state=TemporalState(data.get("temporal_state", "observed")),
        custom_fields=custom_fields,
        source=Source.AGENT,
    )
    
    filepath = md_store.write(event)
    
    registry.index(
        doc_id=str(event.id),
        path=filepath,
        entity_type=EntityType.EVENT,
        name=event.title,
        checksum=md_store._compute_checksum(f"# {event.title}"),
        content=f"# {event.title}",
    )
    
    graph_store.upsert_node(event)
    
    # Auto-create General Info document (always created, even with placeholder)
    initial_context = context or data.get("context") or f"Information about {event.title}."
    _create_general_info_document(
        entity_id=str(event.id),
        entity_type=EntityType.EVENT,
        entity_name=event.title,
        initial_content=initial_context,
        md_store=md_store,
        registry=registry,
    )
    
    # Generate embedding for semantic search
    _queue_embedding_generation(str(event.id))
    
    logger.info(f"Created event: {event.title} ({event.id})")
    
    return UpsertResult(
        action="created",
        entity_id=str(event.id),
        entity={
            "id": str(event.id),
            "title": event.title,
            "type": "event",
            "on_date": event.on_date.isoformat() if event.on_date else None,
        },
    )


# ============================================
# Period Upsert
# ============================================

def upsert_period(
    name: str,
    context: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    data: dict | None = None,
    conversation_id: str | None = None,
) -> UpsertResult:
    """
    Create or update a period entity.
    
    Args:
        name: Period name (descriptive, not user's literal phrase)
        context: Additional context
        start_date: Start date of the period
        end_date: End date of the period
        data: Additional fields
        conversation_id: Conversation ID for context-based resolution
    """
    resolver = _get_resolver()
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    data = data or {}
    
    # Parse dates if strings
    if isinstance(start_date, str):
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            import dateparser
            parsed = dateparser.parse(start_date)
            start_date = parsed.date() if parsed else None
    
    if isinstance(end_date, str):
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            import dateparser
            parsed = dateparser.parse(end_date)
            end_date = parsed.date() if parsed else None
    
    # Check for existing period with same name
    result = resolver.resolve(
        name=name,
        entity_type=EntityType.PERIOD,
        context=context,
    )
    
    if result.needs_confirmation:
        return UpsertResult(
            action="needs_confirmation",
            entity_id=None,
            entity={"name": name, "context": context, "start_date": str(start_date), "end_date": str(end_date), **data},
            candidates=result.candidates,
        )
    
    if result.found:
        # Update existing period with new dates if provided
        entity_id = result.entity_id
        existing = registry.get(entity_id)
        
        # TODO: Update dates if newly provided
        return UpsertResult(
            action="no_change",
            entity_id=entity_id,
            entity=existing,
        )
    
    # Create new period
    custom_fields = data.pop("custom_fields", {}) or {}
    
    period = Period(
        id=uuid4(),
        name=name,
        start_date=start_date,
        end_date=end_date,
        custom_fields=custom_fields,
        source=Source.AGENT,
    )
    
    filepath = md_store.write(period)
    
    registry.index(
        doc_id=str(period.id),
        path=filepath,
        entity_type=EntityType.PERIOD,
        name=period.name,
        checksum=md_store._compute_checksum(f"# {period.name}"),
        content=f"# {period.name}",
    )
    
    graph_store.upsert_node(period)
    
    # Auto-create General Info document (always created, even with placeholder)
    initial_context = context or data.get("context") or f"Information about {period.name}."
    _create_general_info_document(
        entity_id=str(period.id),
        entity_type=EntityType.PERIOD,
        entity_name=period.name,
        initial_content=initial_context,
        md_store=md_store,
        registry=registry,
    )
    
    # Generate embedding for semantic search
    _queue_embedding_generation(str(period.id))
    
    logger.info(f"Created period: {period.name} ({period.id})")
    
    return UpsertResult(
        action="created",
        entity_id=str(period.id),
        entity={
            "id": str(period.id),
            "name": period.name,
            "type": "period",
            "start_date": period.start_date.isoformat() if period.start_date else None,
            "end_date": period.end_date.isoformat() if period.end_date else None,
            "is_complete": period.is_complete,
        },
    )


__all__ = [
    "upsert_person",
    "upsert_project",
    "upsert_goal",
    "upsert_event",
    "upsert_period",
    "_create_person",
]

