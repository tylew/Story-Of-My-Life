"""
CrewAI Agents - Agent definitions for SOML.

Each agent is specialized for a specific domain:
- Ingestion Agent: Extract entities and relationships from text
- Query Agent: Answer questions using the knowledge graph
- Intelligence Agent: Detect patterns, open loops, and synthesize
"""

from datetime import date
from typing import Any

from crewai import Agent
from crewai.tools import tool

from soml.core.config import settings, get_logger
from soml.mcp import tools as mcp_tools

logger = get_logger("crew.agents")


# ============================================
# MCP Tools as CrewAI Tools
# ============================================

@tool("Upsert Person")
def upsert_person_tool(name: str, context: str = "", data: str = "") -> str:
    """
    Create or update a person in the knowledge graph.
    
    Args:
        name: Person's name
        context: Disambiguating context (e.g., "user's father")
        data: JSON string of additional data (email, phone, notes)
    
    Returns:
        Result string with action taken
    """
    import json
    data_dict = json.loads(data) if data else {}
    result = mcp_tools.upsert_person(name, context or None, data_dict)
    return f"Action: {result.action}, ID: {result.entity_id}, Changes: {result.changes}"


@tool("Upsert Project")
def upsert_project_tool(name: str, context: str = "", data: str = "") -> str:
    """
    Create or update a project in the knowledge graph.
    
    Args:
        name: Project name
        context: Disambiguating context
        data: JSON string of additional data
    
    Returns:
        Result string with action taken
    """
    import json
    data_dict = json.loads(data) if data else {}
    result = mcp_tools.upsert_project(name, context or None, data_dict)
    return f"Action: {result.action}, ID: {result.entity_id}"


@tool("Upsert Goal")
def upsert_goal_tool(title: str, context: str = "", data: str = "") -> str:
    """
    Create or update a goal in the knowledge graph.
    
    Args:
        title: Goal title
        context: Additional context
        data: JSON string of additional data
    
    Returns:
        Result string with action taken
    """
    import json
    data_dict = json.loads(data) if data else {}
    result = mcp_tools.upsert_goal(title, context or None, data_dict)
    return f"Action: {result.action}, ID: {result.entity_id}"


@tool("Upsert Event")
def upsert_event_tool(title: str, on_date: str = "", context: str = "", data: str = "") -> str:
    """
    Create or update an event in the knowledge graph.
    
    Args:
        title: Event title
        on_date: Date of the event (ISO format or natural language)
        context: Additional context
        data: JSON string of additional data
    
    Returns:
        Result string with action taken
    """
    import json
    data_dict = json.loads(data) if data else {}
    result = mcp_tools.upsert_event(title, on_date or None, context or None, data_dict)
    return f"Action: {result.action}, ID: {result.entity_id}"


@tool("Upsert Period")
def upsert_period_tool(name: str, context: str = "", start_date: str = "", end_date: str = "") -> str:
    """
    Create or update a period (time span) in the knowledge graph.
    
    Args:
        name: Descriptive name for the period (NOT the user's literal phrase)
        context: Additional context
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.upsert_period(name, context or None, start_date or None, end_date or None)
    return f"Action: {result.action}, ID: {result.entity_id}"


@tool("Link Entities")
def link_entities_tool(source_id: str, target_id: str, rel_type: str, properties: str = "") -> str:
    """
    Create a relationship between two entities.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (family, friend, works_at, invested_in, etc.)
        properties: JSON string of additional properties
    
    Returns:
        Result string with action taken
    """
    import json
    props = json.loads(properties) if properties else {}
    result = mcp_tools.link_entities(source_id, target_id, rel_type, props)
    return f"Action: {result.action}, Relationship ID: {result.relationship_id}"


@tool("Process Extraction")
def process_extraction_tool(entities_json: str, relationships_json: str, conversation_id: str = "") -> str:
    """
    Process a batch of extracted entities and relationships.
    
    This is the main tool for ingestion - handles resolution and creation.
    
    Args:
        entities_json: JSON array of entity dicts [{name, type, context}, ...]
        relationships_json: JSON array of relationship dicts [{source_name, target_name, type}, ...]
        conversation_id: Optional conversation ID for context
    
    Returns:
        Summary of actions taken
    """
    import json
    entities = json.loads(entities_json)
    relationships = json.loads(relationships_json)
    result = mcp_tools.process_extraction(entities, relationships, conversation_id or None)
    
    summary = []
    for e in result.entities:
        summary.append(f"Entity: {e.action}")
    for r in result.relationships:
        summary.append(f"Relationship: {r.action}")
    if result.needs_confirmation:
        summary.append(f"Needs confirmation: {len(result.needs_confirmation)} entities")
    
    return "\n".join(summary)


@tool("Get Entity")
def get_entity_tool(entity_id: str) -> str:
    """
    Get an entity by ID.
    
    Args:
        entity_id: Entity ID
    
    Returns:
        Entity data as JSON string
    """
    import json
    entity = mcp_tools.get_entity(entity_id)
    return json.dumps(entity, default=str) if entity else "Entity not found"


@tool("Search Entities")
def search_entities_tool(query: str, entity_type: str = "", limit: int = 10) -> str:
    """
    Search for entities by name or content.
    
    Args:
        query: Search query
        entity_type: Optional type filter (person, project, goal, event, period)
        limit: Maximum results (default 10)
    
    Returns:
        JSON array of matching entities
    """
    import json
    results = mcp_tools.search_entities(query, entity_type or None, limit)
    return json.dumps(results, default=str)


@tool("Get Relationships")
def get_relationships_tool(entity_id: str, direction: str = "both", rel_type: str = "") -> str:
    """
    Get relationships for an entity.
    
    Args:
        entity_id: Entity ID
        direction: "outgoing", "incoming", or "both"
        rel_type: Optional relationship type filter
    
    Returns:
        JSON array of relationships
    """
    import json
    results = mcp_tools.get_relationships(entity_id, direction, rel_type or None)
    return json.dumps(results, default=str)


@tool("Get Timeline")
def get_timeline_tool(start_date: str = "", end_date: str = "", types: str = "") -> str:
    """
    Get timeline of events.
    
    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        types: Comma-separated list of entity types
    
    Returns:
        JSON array of timeline entries
    """
    import json
    type_list = types.split(",") if types else None
    results = mcp_tools.get_timeline(start_date or None, end_date or None, type_list)
    return json.dumps(results, default=str)


@tool("Detect Open Loops")
def detect_open_loops_tool() -> str:
    """
    Detect open loops (stale relationships, stalled projects, etc.)
    
    Returns:
        JSON array of open loops with urgency
    """
    import json
    loops = mcp_tools.detect_open_loops()
    return json.dumps(loops, default=str)


@tool("Find Duplicates")
def find_duplicates_tool() -> str:
    """
    Find potential duplicate entities in the knowledge graph.
    
    Returns:
        JSON array of duplicate candidate pairs
    """
    import json
    duplicates = mcp_tools.find_duplicates()
    return json.dumps(duplicates, default=str)


@tool("Flag For Review")
def flag_for_review_tool(entity_id: str, reason: str) -> str:
    """
    Flag an entity or document for user review.
    
    Use this when:
    - Information seems incomplete or uncertain
    - Multiple interpretations are possible
    - Data quality is questionable
    - User confirmation would be valuable
    
    This creates an open loop that will be surfaced to the user.
    
    Args:
        entity_id: ID of the entity to flag
        reason: Why this needs review (be specific)
    
    Returns:
        JSON with success status
    """
    import json
    result = mcp_tools.flag_for_review(entity_id, reason)
    return json.dumps(result, default=str)


@tool("Clear Review Flag")
def clear_review_flag_tool(entity_id: str) -> str:
    """
    Clear the review flag from an entity after user review.
    
    Args:
        entity_id: ID of the entity
    
    Returns:
        JSON with success status
    """
    import json
    result = mcp_tools.clear_review_flag(entity_id)
    return json.dumps(result, default=str)


@tool("Get Items Needing Review")
def get_items_needing_review_tool() -> str:
    """
    Get all entities and documents flagged for review.
    
    Returns:
        JSON array of items with id, name, type, and review_reason
    """
    import json
    items = mcp_tools.get_items_needing_review()
    return json.dumps(items, default=str)


# ============================================
# Advanced Search Tools
# ============================================

@tool("Search Documents")
def search_documents_tool(query: str, entity_id: str = "", document_type: str = "") -> str:
    """
    Search through document contents across the knowledge graph.
    
    Use this to find information stored in documents (General Info, notes, etc.)
    This searches the actual CONTENT of documents, not just entity names.
    
    Examples:
    - "wife" → finds documents mentioning someone's wife
    - "funding round" → finds documents about funding
    - "meeting notes from last week" → finds meeting documents
    
    Args:
        query: What to search for (natural language)
        entity_id: Optional - limit search to this entity's documents only
        document_type: Optional - filter by type (general_info, note, meeting, etc.)
    
    Returns:
        JSON array of matching documents with parent entity info and content snippets
    """
    import json
    results = mcp_tools.search_documents(
        query=query,
        entity_id=entity_id or None,
        document_type=document_type or None,
    )
    return json.dumps(results, default=str)


@tool("Find Entities By Name")
def find_entities_by_name_tool(name: str, entity_type: str = "", exact: str = "false") -> str:
    """
    Find entities by name with disambiguation support.
    
    Use this FIRST when a user mentions a name like "Frank" or "Project Alpha".
    Returns all matching entities so you can determine if clarification is needed.
    
    IMPORTANT: If multiple entities match, you should ask the user which one they mean.
    
    Args:
        name: Name to search for (e.g., "Frank", "Alpha", "my project")
        entity_type: Optional type filter (person, project, goal, event, period)
        exact: "true" for exact matches only, "false" (default) includes similar names
    
    Returns:
        JSON array of matching entities with entity_ref markers for linking
    """
    import json
    results = mcp_tools.find_entities_by_name(
        name=name,
        entity_type=entity_type or None,
        exact=exact.lower() == "true",
    )
    
    # Add entity_ref markers
    for r in results:
        eid = r.get("id")
        ename = r.get("name") or r.get("title")
        etype = r.get("type")
        if eid and ename and etype:
            r["entity_ref"] = f"[entity:{eid}:{ename}:{etype}]"
    
    return json.dumps(results, default=str)


@tool("Get Entity With Documents")
def get_entity_with_documents_tool(entity_id: str) -> str:
    """
    Get comprehensive information about an entity including all documents.
    
    Use this after resolving which entity the user means to get full details.
    Returns the entity data, General Info content, all documents, and relationships.
    
    Args:
        entity_id: The entity ID to look up
    
    Returns:
        JSON object with entity, general_info, documents, relationships, and entity_ref
    """
    import json
    result = mcp_tools.get_entity_with_documents(entity_id)
    if not result:
        return "Entity not found"
    
    # Add entity_ref marker
    entity = result.get("entity", {})
    ename = entity.get("name") or entity.get("title")
    etype = entity.get("type")
    if ename and etype:
        result["entity_ref"] = f"[entity:{entity_id}:{ename}:{etype}]"
    
    # Add refs for documents (use [document:id:name] format)
    for doc in result.get("documents", []):
        did = doc.get("id")
        dname = doc.get("title") or doc.get("name")
        if did and dname:
            doc["document_ref"] = f"[document:{did}:{dname}]"
    
    return json.dumps(result, default=str)


@tool("Get General Info")
def get_general_info_tool(entity_id: str) -> str:
    """
    Get the General Info document for an entity.
    
    This contains the AI-managed summary/bio for an entity.
    Use this to quickly check what we know about someone/something.
    
    Args:
        entity_id: The entity ID
    
    Returns:
        JSON object with document content, or "No General Info document"
    """
    import json
    result = mcp_tools.get_general_info(entity_id)
    if result:
        return json.dumps({
            "id": result.get("metadata", {}).get("id"),
            "content": result.get("content", ""),
        }, default=str)
    return "No General Info document found for this entity"


@tool("Semantic Search")
def semantic_search_tool(query: str, entity_type: str = "", limit: int = 10, min_score: float = 0.7) -> str:
    """
    Search using semantic similarity (vector embeddings).
    
    This finds entities whose meaning is HIGHLY relevant to your query,
    even if the exact words don't match.
    
    IMPORTANT: Only results with score >= min_score are returned.
    A score of 0.7+ means strong relevance, 0.8+ means very strong.
    
    Use this for conceptual queries like:
    - "who smokes cigarettes" → finds people with smoking in their notes
    - "projects about automation" 
    - "events related to fundraising"
    
    Args:
        query: Natural language query describing what you're looking for
        entity_type: Optional type filter (person, project, goal, event, period, document)
        limit: Maximum results (default 10)
        min_score: Minimum similarity score threshold (default 0.7)
    
    Returns:
        JSON with matching entities including entity_ref markers for linking.
        Results are filtered to only show highly relevant matches.
        If a document matches, its parent_entity_id shows which person/project it belongs to.
        
        IMPORTANT: When citing results in your answer, include the entity_ref marker
        so the user can click to view the entity.
    """
    import json
    results = mcp_tools.semantic_search(
        query=query,
        limit=limit,
        entity_type=entity_type or None,
    )
    
    # Filter by minimum score
    filtered = [r for r in results if r.get("score", 0) >= min_score]
    
    # Enrich with parent entity info for documents
    enriched = []
    for r in filtered:
        entity = r.get("entity", {})
        name = entity.get("name") or entity.get("title")
        # Neo4j stores as entity_type, registry uses type
        etype = entity.get("entity_type") or entity.get("type")
        eid = entity.get("id")
        
        entry = {
            "name": name,
            "type": etype,
            "score": round(r.get("score", 0), 3),
            "id": eid,
            # Include this marker in your response to create clickable links
            "entity_ref": f"[entity:{eid}:{name}:{etype}]",
        }
        # For documents, include parent info
        if etype == "document":
            parent_id = entity.get("parent_entity_id")
            entry["parent_entity_id"] = parent_id
            entry["document_type"] = entity.get("document_type")
            # Also provide parent ref if available
            if parent_id:
                entry["parent_ref"] = f"[entity:{parent_id}:parent:{entity.get('parent_entity_type', 'entity')}]"
        enriched.append(entry)
    
    if not enriched:
        return json.dumps({"message": "No highly relevant results found (score >= 0.7). Try Search Documents for keyword matching."})
    
    return json.dumps(enriched, default=str)


# ============================================
# Employment Tools
# ============================================

@tool("Set Employment")
def set_employment_tool(person_id: str, organization: str, role: str = "", start_date: str = "") -> str:
    """
    Set a person's current employment.
    
    Use this instead of creating organization entities. Organizations are stored
    as context on the person, not as separate entities.
    
    Args:
        person_id: ID of the person
        organization: Company/organization name (e.g., "Google", "Acme Corp")
        role: Job title (optional)
        start_date: When they started (ISO format, optional)
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.set_employment(person_id, organization, role or None, start_date or None)
    return f"Action: {result.action}, Changes: {result.changes}"


@tool("End Employment")
def end_employment_tool(person_id: str, end_date: str = "", new_organization: str = "") -> str:
    """
    End a person's current employment.
    
    Use this when someone leaves a job. Optionally set their new employer.
    
    Args:
        person_id: ID of the person
        end_date: When they left (ISO format, defaults to today)
        new_organization: New employer if they're changing jobs
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.end_employment(person_id, end_date or None, new_organization or None)
    return f"Action: {result.action}, Changes: {result.changes}"


@tool("Transition Coworker Relationship")
def transition_coworker_relationship_tool(person1_id: str, person2_id: str) -> str:
    """
    Change a works_with relationship to worked_with.
    
    Use this when one person leaves a shared workplace.
    
    Args:
        person1_id: First person's ID
        person2_id: Second person's ID
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.transition_coworker_relationship(person1_id, person2_id)
    return f"Action: {result.action}"


@tool("Find Coworkers")
def find_coworkers_tool(person_id: str, organization: str = "", include_former: bool = False) -> str:
    """
    Find people who work(ed) with a person.
    
    Args:
        person_id: Person to find coworkers for
        organization: Filter by organization (optional)
        include_former: Include former coworkers
    
    Returns:
        JSON array of coworker records
    """
    import json
    results = mcp_tools.find_coworkers(person_id, organization or None, include_former)
    return json.dumps(results, default=str)


# ============================================
# Relationship Management Tools
# ============================================

@tool("Get Entity Relationships")
def get_entity_relationships_tool(entity_id: str, include_details: bool = True) -> str:
    """
    Get all relationships for an entity.
    
    ALWAYS use this before proposing relationship changes to see what already exists.
    
    Args:
        entity_id: Entity ID to get relationships for
        include_details: Include name/type of related entities
    
    Returns:
        JSON array of relationships with full context
    """
    import json
    results = mcp_tools.get_entity_relationships(entity_id, "both", include_details)
    return json.dumps(results, default=str)


@tool("Add Relationship")
def add_relationship_tool(source_id: str, target_id: str, rel_type: str, reason: str = "") -> str:
    """
    Add a new relationship between entities.
    
    Use this for creating completely new relationships.
    For updating existing ones, use Replace Relationship.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type (friend, family, works_with, invested_in, etc.)
        reason: Why this relationship is being created
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.add_relationship(source_id, target_id, rel_type, reason or None)
    return f"Action: {result.action}, ID: {result.relationship_id}, Error: {result.error}"


@tool("Replace Relationship")
def replace_relationship_tool(source_id: str, target_id: str, old_type: str, new_type: str, reason: str = "") -> str:
    """
    Replace an existing relationship type with a new one.
    
    Use this for transitions like:
    - works_with → worked_with (when someone leaves a job)
    - acquaintance → friend (relationship strengthened)
    - friend → partner (relationship upgraded)
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        old_type: Current relationship type to replace
        new_type: New relationship type
        reason: Why this change is happening
    
    Returns:
        Result string with action taken
    """
    result = mcp_tools.replace_relationship(source_id, target_id, old_type, new_type, reason or None)
    return f"Action: {result.action}, Error: {result.error}"


@tool("Remove Relationship")
def remove_relationship_tool(source_id: str, target_id: str, rel_type: str) -> str:
    """
    Remove a relationship between entities.
    
    Args:
        source_id: Source entity ID
        target_id: Target entity ID
        rel_type: Relationship type to remove
    
    Returns:
        Result string indicating success
    """
    success = mcp_tools.unlink_entities(source_id, target_id, rel_type)
    return f"Removed: {success}"


@tool("Analyze Relationships For Changes")
def analyze_relationships_tool(entity_ids: str, context: str) -> str:
    """
    Analyze entities and their existing relationships to propose changes.
    
    Call this before making relationship proposals. It returns:
    - Entity names for context
    - All existing relationships between the entities
    
    Args:
        entity_ids: Comma-separated list of entity IDs
        context: The user input that triggered this analysis
    
    Returns:
        JSON with entity info and existing relationships
    """
    import json
    ids = [id.strip() for id in entity_ids.split(",")]
    result = mcp_tools.propose_relationship_changes(ids, context)
    return json.dumps(result, default=str)


@tool("Apply Relationship Proposal")
def apply_relationship_proposal_tool(action: str, source_id: str, target_id: str, new_type: str = "", old_type: str = "", reason: str = "") -> str:
    """
    Apply a user-approved relationship proposal.
    
    Call this ONLY after user has approved the proposed change.
    
    Args:
        action: "add", "replace", or "remove"
        source_id: Source entity ID
        target_id: Target entity ID
        new_type: New relationship type (for add/replace)
        old_type: Existing relationship type (for replace/remove)
        reason: Reason for the change
    
    Returns:
        Result string with action taken
    """
    proposal = {
        "action": action,
        "source_id": source_id,
        "target_id": target_id,
        "new_type": new_type or None,
        "old_type": old_type or None,
        "reason": reason or None,
    }
    result = mcp_tools.apply_relationship_proposal(proposal)
    return f"Action: {result.action}, Error: {result.error}"


# ============================================
# Agent Factories
# ============================================

def create_ingestion_agent(llm_config: dict | None = None) -> Agent:
    """
    Create the ingestion agent that extracts entities and relationships.
    
    This agent uses process_extraction_tool as its primary tool,
    which handles all the complexity of entity resolution internally.
    """
    today = date.today().isoformat()
    
    return Agent(
        role="Knowledge Extractor",
        goal="Extract entities, relationships, and temporal information from user input",
        backstory=f"""You are a knowledge extraction specialist for a personal knowledge graph.
        
        Your job is to identify:
        - PERSON: People the user knows (with context like "my dad", "coworker")
        - PROJECT: User's personal projects and initiatives (NOT external companies)
        - GOAL: Personal objectives the user is working toward
        - EVENT: Specific occurrences with dates
        - PERIOD: Time spans ("job at Company X", "college years")
        - Relationships between entities
        
        Today's date is {today}. Use this to resolve relative dates.
        
        *** RELATIONSHIP PROPOSALS ***
        
        When proposing relationships:
        1. ALWAYS check existing relationships first using get_entity_relationships_tool
        2. Decide if you need to ADD a new relationship or REPLACE an existing one
        3. Propose changes with clear reasoning
        4. Your proposals will be shown to the user for approval
        
        Relationship transitions (use replace, not add):
        - works_with → worked_with (when someone leaves)
        - acquaintance → friend (relationship strengthened)
        - friend → partner (relationship upgraded)
        
        *** ORGANIZATIONS/COMPANIES ARE NOT ENTITIES ***
        
        External companies like Google, Apple, Acme Corp are NOT project entities.
        They are EMPLOYMENT CONTEXT stored on Person entities.
        
        When you see "John works at Google":
        1. Create Person: John
        2. Use set_employment_tool to record John works at Google
        3. Do NOT create a Project entity for Google
        
        When you see "John and Bill work together at Google":
        1. Create Person: John, set employment to Google
        2. Create Person: Bill, set employment to Google
        3. PROPOSE Relationship: John <-> Bill, type: works_with (ADD)
        
        When you see "Bill left Google and joined Yahoo":
        1. Use end_employment_tool for Bill with new_organization="Yahoo"
        2. PROPOSE: Replace John-Bill works_with → worked_with
        
        ENTITY DISTINCTIONS:
        - Events: Specific occurrences ("meeting tomorrow", "birthday on June 5")
        - Periods: Time spans ("time at Google", "Q1 sprint", "new job phase")
        - Projects: User's OWN projects, not external companies
        
        For periods, always give them descriptive names (e.g., "Employment at Brightfield AI")
        not the user's literal phrase ("new phase of my life").""",
        tools=[
            process_extraction_tool,
            search_entities_tool,
            get_entity_tool,
            get_entity_relationships_tool,
            analyze_relationships_tool,
            set_employment_tool,
            end_employment_tool,
            transition_coworker_relationship_tool,
            find_coworkers_tool,
            upsert_person_tool,
            link_entities_tool,
        ],
        verbose=False,
        allow_delegation=False,
    )


def create_query_agent(llm_config: dict | None = None) -> Agent:
    """
    Create the query agent that answers questions about the knowledge graph.
    """
    return Agent(
        role="Knowledge Navigator",
        goal="Answer questions accurately using the personal knowledge graph",
        backstory="""You are a knowledge navigator for a personal knowledge graph.
        
        You help the user explore their stored memories, relationships, projects, and events.
        Always search the graph before answering - don't make up information.
        
        **CRITICAL WORKFLOW FOR QUESTIONS:**
        
        1. **"Who/What does X" Questions - USE SEMANTIC SEARCH FIRST:**
           When the user asks about characteristics/attributes/behaviors (like "who smokes", 
           "who works at Google", "what project involves AI"), ALWAYS use Semantic Search first.
           - Semantic Search finds entities whose documents CONTAIN that information
           - Example: "who smokes cigarettes" → Semantic Search for "smokes cigarettes"
           - The results will show which person/entity has that in their documents
           - Return the ENTITY (person), not just the document
        
        2. **Name Resolution**: When a user mentions a specific name (like "Frank", "Project Alpha"),
           use Find Entities By Name to locate them.
           - If multiple matches: Ask the user "Which [name] do you mean?" and list the options
           - If one match: Proceed with that entity
           - If no matches: Tell the user you couldn't find that entity
        
        3. **Entity-Specific Search**: When looking for specific information about a KNOWN entity:
           - Use Get Entity With Documents to get their full info including documents
           - Use Search Documents with entity_id to search within their documents
           - Example: "Frank's wife" → First find Frank, then search his documents for "wife"
        
        4. **Global Search**: When the user doesn't remember WHO has certain info:
           - Use Semantic Search (preferred) or Search Documents without entity_id
           - Example: "who has a wife I made notes on" → Semantic Search for "wife"
           - Return the parent entity, not just the document
        
        5. **Relationships**: Use Get Relationships to understand connections between entities
        
        **RESPONSE FORMAT:**
        - Always cite which entity (person/project) the information came from
        - CRITICAL: When mentioning an entity, include the entity_ref marker from the search results
          Example: "Celine [entity:abc123:Celine:person] smokes cigarettes according to her notes."
        - The entity_ref format is: [entity:id:name:type]
        - If information is in a document, mention the parent entity
        - If information is not found, say so clearly
        - If clarification is needed (ambiguous name), ask before proceeding""",
        tools=[
            # Entity resolution
            find_entities_by_name_tool,
            get_entity_tool,
            get_entity_with_documents_tool,
            # Search tools
            search_entities_tool,
            search_documents_tool,
            semantic_search_tool,  # Vector similarity search
            get_general_info_tool,
            # Context tools
            get_relationships_tool,
            get_timeline_tool,
        ],
        verbose=False,
        allow_delegation=False,
    )


def create_intelligence_agent(llm_config: dict | None = None) -> Agent:
    """
    Create the intelligence agent that analyzes patterns and open loops.
    """
    return Agent(
        role="Knowledge Analyst",
        goal="Detect patterns, open loops, review flags, duplicates, and synthesize insights",
        backstory="""You are an intelligence analyst for a personal knowledge graph.
        
        You help the user by:
        - Detecting items flagged for review (highest priority)
        - Detecting stale relationships that need attention
        - Finding stalled projects
        - Identifying potential duplicate entities
        - Synthesizing insights from patterns
        
        Open loops include items flagged for review by the system.
        These have a review_reason explaining why they need attention.
        
        Be proactive in suggesting actions but don't overwhelm the user.""",
        tools=[
            detect_open_loops_tool,  # Now includes needs_review items
            find_duplicates_tool,
            get_items_needing_review_tool,  # Dedicated review tool
            clear_review_flag_tool,  # For clearing after review
            search_entities_tool,
            get_relationships_tool,
            get_timeline_tool,
        ],
        verbose=False,
        allow_delegation=False,
    )

