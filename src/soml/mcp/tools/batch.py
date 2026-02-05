"""
MCP Tools - Batch processing tools.

Tools for processing multiple entities at once:
- process_extraction: Process extracted entities and relationships from LLM
"""

import re

from soml.mcp.tools.base import (
    ProcessResult,
    LinkResult,
    logger,
)
from soml.mcp.tools.entity import (
    upsert_person,
    upsert_project,
    upsert_goal,
    upsert_event,
    upsert_period,
)
from soml.mcp.tools.employment import set_employment
from soml.mcp.tools.relationship import link_entities
from soml.mcp.resolution import EntityResolver


def _extract_employment_from_context(context: str | None) -> tuple[str | None, str | None]:
    """
    Extract employment information from context string.
    
    Returns:
        Tuple of (organization_name, role) or (None, None)
    """
    if not context:
        return None, None
    
    # Patterns for employment (case insensitive)
    patterns = [
        r"works?\s+(?:at|for)\s+([A-Z][A-Za-z0-9\s&]+)",  # works at Google
        r"employed\s+(?:at|by)\s+([A-Z][A-Za-z0-9\s&]+)",  # employed at Google
        r"(?:is\s+)?(?:a\s+)?(?:\w+\s+)?at\s+([A-Z][A-Za-z0-9\s&]+)",  # engineer at Google
    ]
    
    for pattern in patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            org = match.group(1).strip()
            # Clean up common suffixes
            org = re.sub(r'\s+(company|corp|inc|llc|ltd)\.?$', '', org, flags=re.IGNORECASE)
            if org and len(org) > 1:
                return org, None
    
    return None, None


def _resolve_entity_by_name(resolver: EntityResolver, name: str) -> str | None:
    """
    Resolve an entity name to an existing entity ID by searching the registry.
    
    Searches across all entity types to find the best match.
    
    Args:
        resolver: EntityResolver instance
        name: Name to resolve
    
    Returns:
        Entity ID if found, None otherwise
    """
    from soml.core.types import EntityType
    
    # Try each entity type
    for entity_type in [EntityType.PERSON, EntityType.PROJECT, EntityType.PERIOD, EntityType.EVENT, EntityType.GOAL]:
        result = resolver.resolve(name=name, entity_type=entity_type)
        if result.found and result.entity_id:
            return result.entity_id
    
    # Also try fuzzy matching across all types via registry search
    from soml.storage.registry import RegistryStore
    registry = RegistryStore()
    
    # Search by name
    matches = registry.search(name, limit=5)
    if matches:
        # Check for high-confidence match (exact or near-exact name match)
        for match in matches:
            match_name = match.get("name", "").lower()
            search_name = name.lower()
            
            # Exact match
            if match_name == search_name:
                return match.get("id")
            
            # Check if one contains the other (e.g., "Hansji" matches "Hansji Corporation")
            if search_name in match_name or match_name in search_name:
                # Calculate similarity
                shorter = min(len(match_name), len(search_name))
                longer = max(len(match_name), len(search_name))
                if shorter / longer > 0.5:  # At least 50% overlap
                    return match.get("id")
    
    return None


def _is_organization_entity(name: str, entity_type: str, context: str | None, all_entities: list[dict]) -> bool:
    """
    Check if this entity is actually an organization (employer) that shouldn't be a separate entity.
    """
    if entity_type.lower() != "project":
        return False
    
    name_lower = name.lower()
    
    # Check if any person has this as their employer in context
    for entity in all_entities:
        if entity.get("type", "").lower() == "person":
            ent_context = (entity.get("context", "") or "").lower()
            if name_lower in ent_context:
                patterns = ["works at", "works for", "employed at", "employed by"]
                if any(p in ent_context for p in patterns):
                    return True
    
    # Check context for organization-like terms
    if context:
        context_lower = context.lower()
        org_indicators = ["company", "employer", "workplace", "corporation", "where"]
        if any(ind in context_lower for ind in org_indicators):
            return True
    
    return False


def process_extraction(
    entities: list[dict],
    relationships: list[dict],
    conversation_id: str | None = None,
) -> ProcessResult:
    """
    Process a batch of extracted entities and relationships.
    
    This is the main entry point for ingestion pipelines.
    Automatically handles employment information:
    - Extracts "works at X" from person context
    - Sets employment on person entities
    - Filters out organization entities (companies are not Project entities)
    - Creates works_with relationships for coworkers
    
    Args:
        entities: List of entity dicts with {name, type, context, ...}
        relationships: List of relationship dicts with {source_name, target_name, type, ...}
        conversation_id: Conversation ID for context tracking
    
    Returns:
        ProcessResult with results for each entity and relationship
    """
    result = ProcessResult()
    entity_id_map: dict[str, str] = {}  # name -> id
    employment_map: dict[str, str] = {}  # person_id -> organization
    
    # First pass: Filter out organization entities
    filtered_entities = []
    for entity_data in entities:
        name = entity_data.get("name", "")
        entity_type = entity_data.get("type", "person").lower()
        context = entity_data.get("context")
        
        # Skip organizations masquerading as projects
        if _is_organization_entity(name, entity_type, context, entities):
            logger.info(f"Skipping organization entity: {name} (not creating as project)")
            continue
        
        filtered_entities.append(entity_data)
    
    # Process entities
    for entity_data in filtered_entities:
        name = entity_data.get("name", "")
        entity_type = entity_data.get("type", "person").lower()
        context = entity_data.get("context")
        data = {k: v for k, v in entity_data.items() if k not in ["name", "type", "context"]}
        
        # Call appropriate upsert
        if entity_type == "person":
            upsert_result = upsert_person(name, context, data, conversation_id)
            
            # Extract and set employment if mentioned in context
            if upsert_result.entity_id:
                org, role = _extract_employment_from_context(context)
                if org:
                    emp_result = set_employment(
                        upsert_result.entity_id,
                        org,
                        role,
                    )
                    if emp_result.action == "updated":
                        employment_map[upsert_result.entity_id] = org
                        logger.info(f"Set employment for {name}: {org}")
                        
        elif entity_type == "project":
            upsert_result = upsert_project(name, context, data, conversation_id)
        elif entity_type == "goal":
            upsert_result = upsert_goal(name, context, data, conversation_id)
        elif entity_type == "event":
            upsert_result = upsert_event(name, entity_data.get("on_date"), context, data, conversation_id)
        elif entity_type == "period":
            upsert_result = upsert_period(
                name, context,
                entity_data.get("start_date"),
                entity_data.get("end_date"),
                data, conversation_id
            )
        else:
            # Default to person if unknown
            upsert_result = upsert_person(name, context, data, conversation_id)
        
        result.entities.append(upsert_result)
        
        if upsert_result.entity_id:
            entity_id_map[name] = upsert_result.entity_id
        
        if upsert_result.action == "needs_confirmation":
            result.needs_confirmation.append({
                "name": name,
                "type": entity_type,
                "candidates": upsert_result.candidates,
            })
    
    # Auto-create works_with relationships for people at the same organization
    orgs_to_people: dict[str, list[str]] = {}
    for person_id, org in employment_map.items():
        org_key = org.lower()
        if org_key not in orgs_to_people:
            orgs_to_people[org_key] = []
        orgs_to_people[org_key].append(person_id)
    
    for org, people_ids in orgs_to_people.items():
        if len(people_ids) > 1:
            for i, p1_id in enumerate(people_ids):
                for p2_id in people_ids[i+1:]:
                    link_result = link_entities(
                        source_id=p1_id,
                        target_id=p2_id,
                        rel_type="works_with",
                        properties={
                            "context": f"Both work at {org}",
                            "source": "agent",
                            "confidence": 0.9,  # High confidence since we have explicit employment data
                        },
                    )
                    if link_result.action != "failed":
                        result.relationships.append(link_result)
                        logger.info(f"Created works_with relationship at {org}")
    
    # Process explicit relationships
    # Use entity resolver to find existing entities that may not be in the current batch
    resolver = EntityResolver()
    
    for rel_data in relationships:
        source_name = rel_data.get("source_name", "")
        target_name = rel_data.get("target_name", "")
        rel_type = rel_data.get("type", "related_to")
        
        # Skip works_at relationships - handled by employment
        if rel_type.lower() in ["works_at", "employed_at", "employed_by"]:
            logger.info(f"Skipping works_at relationship - employment set on person")
            continue
        
        # Try to get IDs from current batch first
        source_id = entity_id_map.get(source_name)
        target_id = entity_id_map.get(target_name)
        
        # If not in current batch, search the registry for existing entities
        if not source_id:
            source_id = _resolve_entity_by_name(resolver, source_name)
            if source_id:
                logger.info(f"Resolved source '{source_name}' to existing entity: {source_id}")
        
        if not target_id:
            target_id = _resolve_entity_by_name(resolver, target_name)
            if target_id:
                logger.info(f"Resolved target '{target_name}' to existing entity: {target_id}")
        
        if not source_id or not target_id:
            missing = []
            if not source_id:
                missing.append(source_name)
            if not target_id:
                missing.append(target_name)
            result.relationships.append(LinkResult(
                action="failed",
                error=f"Could not resolve entity: {', '.join(missing)}",
            ))
            continue
        
        # Build rich relationship properties
        rel_properties = {
            "notes": rel_data.get("reason"),
            "context": rel_data.get("context"),
            "source_text": rel_data.get("source_text"),
            "source": "agent",
        }
        
        # Include optional rich data if provided
        if rel_data.get("strength"):
            rel_properties["strength"] = rel_data.get("strength")
        if rel_data.get("sentiment"):
            rel_properties["sentiment"] = rel_data.get("sentiment")
        if rel_data.get("confidence"):
            rel_properties["confidence"] = rel_data.get("confidence")
        if rel_data.get("started_at"):
            rel_properties["started_at"] = rel_data.get("started_at")
        
        # Remove None values
        rel_properties = {k: v for k, v in rel_properties.items() if v is not None}
        
        link_result = link_entities(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            properties=rel_properties,
        )
        result.relationships.append(link_result)
    
    # Update conversation context
    if conversation_id and entity_id_map:
        try:
            from soml.storage.conversations import ConversationStore
            conv_store = ConversationStore()
            for name, entity_id in entity_id_map.items():
                conv_store.update_entity_context(conversation_id, name, entity_id)
        except Exception as e:
            logger.warning(f"Failed to update conversation context: {e}")
    
    return result


__all__ = [
    "process_extraction",
    "_extract_employment_from_context",
    "_is_organization_entity",
    "_resolve_entity_by_name",
]

