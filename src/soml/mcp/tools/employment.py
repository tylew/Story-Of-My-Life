"""
MCP Tools - Employment management tools.

Tools for managing person employment history:
- set_employment: Set/update current employment
- end_employment: End current employment
- transition_coworker_relationship: works_with -> worked_with
- find_coworkers: Find people who work/worked together
"""

from datetime import datetime, date
from uuid import UUID

from soml.core.types import (
    EmploymentRecord,
    EntityType,
    Person,
    Source,
)
from soml.mcp.tools.base import (
    UpsertResult,
    LinkResult,
    _get_graph_store,
    _get_md_store,
    _get_registry,
    logger,
)


def set_employment(
    person_id: str,
    organization: str,
    role: str | None = None,
    start_date: str | None = None,
) -> UpsertResult:
    """
    Set or update a person's current employment.
    
    This tool:
    1. Marks any previous employment as ended
    2. Sets new current employment
    3. Updates the person's bio/notes
    
    Note: Organizations are NOT entities - they're stored as context on the person.
    
    Args:
        person_id: ID of the person
        organization: Company/org name (e.g., "Google", "Acme Corp")
        role: Job title (optional)
        start_date: When they started (ISO format, optional)
    
    Returns:
        UpsertResult with updated person
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # Get existing person
    existing = registry.get(person_id)
    if not existing or existing.get("type") != "person":
        return UpsertResult(
            action="no_change",
            entity_id=person_id,
            entity=None,
            error=f"Person {person_id} not found",
        )
    
    # Read the markdown doc
    md_doc = md_store.read_by_id(person_id, EntityType.PERSON)
    if not md_doc:
        return UpsertResult(
            action="no_change",
            entity_id=person_id,
            entity=None,
            error=f"Could not read person document",
        )
    
    metadata = md_doc.get("metadata", {})
    
    # Parse existing employment history
    employment_history = metadata.get("employment_history", [])
    
    # End any current employment
    for emp in employment_history:
        if emp.get("is_current"):
            emp["is_current"] = False
            emp["end_date"] = emp.get("end_date") or date.today().isoformat()
    
    # Add new employment
    parsed_start = None
    if start_date:
        try:
            parsed_start = date.fromisoformat(start_date)
        except:
            pass
    
    employment_history.append({
        "organization": organization,
        "role": role,
        "start_date": parsed_start.isoformat() if parsed_start else None,
        "end_date": None,
        "is_current": True,
    })
    
    # Update metadata
    metadata["current_employer"] = organization
    metadata["employment_history"] = employment_history
    
    # Update notes with employment info
    existing_notes = metadata.get("notes", "") or ""
    emp_note = f"Works at {organization}"
    if role:
        emp_note += f" as {role}"
    if parsed_start:
        emp_note += f" (since {parsed_start})"
    
    if organization not in existing_notes:
        metadata["notes"] = f"{existing_notes}\n\n{emp_note}".strip()
    
    # Rebuild Person and save
    try:
        emp_records = []
        for emp in employment_history:
            if isinstance(emp, dict):
                # Parse dates if they're strings
                emp_copy = emp.copy()
                if emp_copy.get("start_date") and isinstance(emp_copy["start_date"], str):
                    try:
                        emp_copy["start_date"] = date.fromisoformat(emp_copy["start_date"])
                    except:
                        emp_copy["start_date"] = None
                if emp_copy.get("end_date") and isinstance(emp_copy["end_date"], str):
                    try:
                        emp_copy["end_date"] = date.fromisoformat(emp_copy["end_date"])
                    except:
                        emp_copy["end_date"] = None
                emp_records.append(EmploymentRecord(**emp_copy))
            else:
                emp_records.append(emp)
        
        person = Person(
            id=UUID(person_id),
            name=metadata.get("name"),
            disambiguator=metadata.get("disambiguator"),
            email=metadata.get("email"),
            phone=metadata.get("phone"),
            current_employer=organization,
            employment_history=emp_records,
            custom_fields=metadata.get("custom_fields", {}),
            created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
            source=Source(metadata.get("source", "agent")),
        )
        
        filepath = md_store.write(person)
        logger.info(f"Set employment for {person.name}: {organization}")
    except Exception as e:
        logger.error(f"Error setting employment: {e}")
        return UpsertResult(
            action="no_change",
            entity_id=person_id,
            entity=None,
            error=str(e),
        )
    
    # Update registry
    registry.index(
        doc_id=person_id,
        path=filepath,
        entity_type=EntityType.PERSON,
        name=person.name,
        checksum=md_store._compute_checksum(md_doc.get("content", "")),
        content=md_doc.get("content", ""),
    )
    
    # Update graph
    graph_store.upsert_node(person)
    
    logger.info(f"Set employment for {person.name}: {organization}")
    
    return UpsertResult(
        action="updated",
        entity_id=person_id,
        entity={
            "id": person_id,
            "name": person.name,
            "current_employer": organization,
        },
        changes=[f"Now works at {organization}" + (f" as {role}" if role else "")],
    )


def end_employment(
    person_id: str,
    end_date: str | None = None,
    new_organization: str | None = None,
) -> UpsertResult:
    """
    End a person's current employment.
    
    This tool:
    1. Marks current employment as ended
    2. Updates their employment history
    3. Optionally sets new employment
    
    Args:
        person_id: ID of the person
        end_date: When they left (ISO format, defaults to today)
        new_organization: If they're moving to a new job
    
    Returns:
        UpsertResult with updated person
    """
    registry = _get_registry()
    md_store = _get_md_store()
    graph_store = _get_graph_store()
    
    # Get existing person
    existing = registry.get(person_id)
    if not existing or existing.get("type") != "person":
        return UpsertResult(
            action="no_change",
            entity_id=person_id,
            entity=None,
            error=f"Person {person_id} not found",
        )
    
    # Read the markdown doc
    md_doc = md_store.read_by_id(person_id, EntityType.PERSON)
    if not md_doc:
        return UpsertResult(
            action="no_change",
            entity_id=person_id,
            entity=None,
            error=f"Could not read person document",
        )
    
    metadata = md_doc.get("metadata", {})
    employment_history = metadata.get("employment_history", [])
    
    # Parse end date
    parsed_end = date.today()
    if end_date:
        try:
            parsed_end = date.fromisoformat(end_date)
        except:
            pass
    
    changes = []
    old_employer = metadata.get("current_employer")
    
    # End current employment
    for emp in employment_history:
        if emp.get("is_current"):
            emp["is_current"] = False
            emp["end_date"] = parsed_end.isoformat()
            changes.append(f"Left {emp.get('organization')} on {parsed_end}")
    
    # Update notes
    existing_notes = metadata.get("notes", "") or ""
    if old_employer:
        # Update "Works at X" to "Worked at X until..."
        existing_notes = existing_notes.replace(
            f"Works at {old_employer}",
            f"Worked at {old_employer} until {parsed_end}"
        )
        metadata["notes"] = existing_notes
    
    # Handle new employment
    if new_organization:
        employment_history.append({
            "organization": new_organization,
            "role": None,
            "start_date": parsed_end.isoformat(),
            "end_date": None,
            "is_current": True,
        })
        metadata["current_employer"] = new_organization
        changes.append(f"Joined {new_organization}")
        
        # Add to notes
        metadata["notes"] = f"{existing_notes}\n\nNow works at {new_organization} (since {parsed_end})".strip()
    else:
        metadata["current_employer"] = None
    
    metadata["employment_history"] = employment_history
    
    # Rebuild Person and save
    person = Person(
        id=UUID(person_id),
        name=metadata.get("name"),
        disambiguator=metadata.get("disambiguator"),
        email=metadata.get("email"),
        phone=metadata.get("phone"),
        current_employer=metadata.get("current_employer"),
        employment_history=[
            EmploymentRecord(**emp) if isinstance(emp, dict) else emp
            for emp in employment_history
        ],
        custom_fields=metadata.get("custom_fields", {}),
        created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
        source=Source(metadata.get("source", "agent")),
    )
    
    filepath = md_store.write(person)
    
    # Update registry
    registry.index(
        doc_id=person_id,
        path=filepath,
        entity_type=EntityType.PERSON,
        name=person.name,
        checksum=md_store._compute_checksum(md_doc.get("content", "")),
        content=md_doc.get("content", ""),
    )
    
    # Update graph
    graph_store.upsert_node(person)
    
    logger.info(f"Ended employment for {person.name}")
    
    return UpsertResult(
        action="updated",
        entity_id=person_id,
        entity={
            "id": person_id,
            "name": person.name,
            "current_employer": metadata.get("current_employer"),
        },
        changes=changes,
    )


def transition_coworker_relationship(
    person1_id: str,
    person2_id: str,
    from_type: str = "works_with",
    to_type: str = "worked_with",
) -> LinkResult:
    """
    Transition a coworker relationship from current to past.
    
    When someone leaves a shared workplace, their 'works_with'
    relationship should become 'worked_with'.
    
    Args:
        person1_id: First person's ID
        person2_id: Second person's ID
        from_type: Current relationship type (default: works_with)
        to_type: New relationship type (default: worked_with)
    
    Returns:
        LinkResult indicating what was changed
    """
    graph_store = _get_graph_store()
    
    try:
        # Find existing relationship
        rels = graph_store.get_relationships(person1_id)
        
        target_rel = None
        for rel in rels:
            if (rel.get("target_id") == person2_id or rel.get("source_id") == person2_id):
                if rel.get("relationship_type") == from_type:
                    target_rel = rel
                    break
        
        if not target_rel:
            return LinkResult(
                action="failed",
                error=f"No '{from_type}' relationship found between these people",
            )
        
        # Update the relationship
        graph_store.update_relationship(
            target_rel["id"],
            relationship_type=to_type,
        )
        
        logger.info(f"Transitioned relationship {person1_id} <-> {person2_id}: {from_type} → {to_type}")
        
        return LinkResult(
            action="updated",
            relationship_id=target_rel["id"],
        )
        
    except Exception as e:
        logger.error(f"Failed to transition relationship: {e}")
        return LinkResult(
            action="failed",
            error=str(e),
        )


def find_coworkers(
    person_id: str,
    organization: str | None = None,
    include_former: bool = False,
) -> list[dict]:
    """
    Find people who work/worked with a person.
    
    Args:
        person_id: Person to find coworkers for
        organization: Filter by organization (optional)
        include_former: Include former coworkers
    
    Returns:
        List of coworker records with relationship info
    """
    graph_store = _get_graph_store()
    registry = _get_registry()
    
    rels = graph_store.get_relationships(person_id)
    
    coworkers = []
    for rel in rels:
        rel_type = rel.get("relationship_type", "")
        
        # Check if it's a coworker relationship
        is_current = rel_type in ["works_with", "coworker"]
        is_former = rel_type in ["worked_with", "former_coworker"]
        
        if not is_current and not (include_former and is_former):
            continue
        
        # Get the other person
        other_id = rel.get("target_id") if rel.get("source_id") == person_id else rel.get("source_id")
        other = registry.get(other_id)
        
        if not other:
            continue
        
        # Filter by organization if specified
        if organization:
            other_employer = other.get("current_employer", "")
            if organization.lower() not in (other_employer or "").lower():
                continue
        
        coworkers.append({
            "id": other_id,
            "name": other.get("name"),
            "relationship": rel_type,
            "current": is_current,
            "organization": rel.get("context", {}).get("organization"),
        })
    
    return coworkers


__all__ = [
    "set_employment",
    "end_employment",
    "transition_coworker_relationship",
    "find_coworkers",
]

