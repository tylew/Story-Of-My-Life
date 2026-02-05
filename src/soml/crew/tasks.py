"""
CrewAI Tasks - Task definitions for SOML workflows.

Tasks are the work units that agents execute.
Each task has a description, expected output, and assigned agent.
"""

from crewai import Task, Agent
from typing import Any


def create_extraction_task(
    agent: Agent,
    user_input: str,
    conversation_id: str | None = None,
    context: list[dict] | None = None,
) -> Task:
    """
    Create a task for extracting entities and relationships from user input.
    
    Args:
        agent: The ingestion agent to assign this task to
        user_input: The user's input text
        conversation_id: Optional conversation ID for context
        context: Optional list of previous messages for context
    
    Returns:
        CrewAI Task for extraction
    """
    context_str = ""
    if context:
        context_str = "\n".join([
            f"{m['role']}: {m['content']}" 
            for m in context[-5:]
        ])
        context_str = f"\n\nConversation context:\n{context_str}"
    
    return Task(
        description=f"""Extract entities and relationships from the following user input.

User input: "{user_input}"{context_str}

*** CRITICAL: CONTEXT MUST INCLUDE ALL INFORMATION ***

When extracting entities, the "context" field MUST include ALL relevant information about them:
- Relationship to user ("my friend", "my dad", "coworker")  
- Employment ("works at Google", "employed at Acme")
- Role/title ("CEO", "engineer")
- Any other distinguishing info

Example: "My friend John works at Google"
- Extract: name="John", type="person", context="friend, works at Google"
- The system will automatically detect "works at Google" and set employment

Example: "Bill is the CEO at Acme Corp"
- Extract: name="Bill", type="person", context="CEO at Acme Corp"

*** DO NOT CREATE COMPANY/ORGANIZATION ENTITIES ***
Companies mentioned as employers (Google, Acme, etc.) are NOT Project entities.
They get stored as employment data on the Person.

Steps:
1. Identify all PEOPLE mentioned - include ALL context info about them
2. Search for existing entities before creating new ones
3. Use process_extraction_tool with complete context strings
4. Identify relationships between PEOPLE (friend, family, works_with, etc.)
5. Create any Period, Event, or Goal entities (NOT companies)

IMPORTANT:
- Context field = ALL info about the person (relationship + employment + role)
- Projects = USER'S personal projects, not external companies
- For periods, give descriptive names, not literal user phrases
- Today's date context is provided in my backstory

Return a JSON summary of what was extracted.
""",
        expected_output="""A JSON object with:
- entities: list of extracted entities with their IDs and FULL context
- relationships: list of relationships created
- needs_confirmation: any ambiguous entities that need user input
""",
        agent=agent,
    )


def create_query_task(
    agent: Agent,
    question: str,
    context: list[dict] | None = None,
) -> Task:
    """
    Create a task for answering a question about the knowledge graph.
    
    Args:
        agent: The query agent to assign this task to
        question: The user's question
        context: Optional conversation context
    
    Returns:
        CrewAI Task for answering
    """
    context_str = ""
    if context:
        context_str = "\n".join([
            f"{m['role']}: {m['content']}" 
            for m in context[-3:]
        ])
        context_str = f"\n\nConversation context:\n{context_str}"
    
    return Task(
        description=f"""Answer the following question using the knowledge graph.

Question: "{question}"{context_str}

**REQUIRED WORKFLOW:**

1. **If the question mentions a name** (person, project, etc.):
   - Use "Find Entities By Name" FIRST to find matching entities
   - If MULTIPLE matches: Return a clarifying question asking which one they mean
   - If ONE match: Continue to gather information about that entity
   - If NO matches: Tell them you couldn't find that entity

2. **If the question asks about information within an entity** (e.g., "Frank's wife", "notes on Alpha"):
   - First resolve which entity using step 1
   - Then use "Search Documents" with that entity_id to find the specific information
   - Or use "Get Entity With Documents" to see all their info

3. **If the question is "who has X" or "find the person with X"** (cross-entity search):
   - Use "Search Documents" WITHOUT entity_id to search ALL documents
   - Report which entity's documents contain the match

4. **For relationship questions**:
   - Use "Get Relationships" to find connections between entities

**IMPORTANT:**
- Do NOT make up information. Only report what you find.
- If name is ambiguous, ALWAYS ask for clarification before answering
- Cite your sources (which entity/document the info came from)
""",
        expected_output="""One of:
1. A direct answer with sources cited (if information found)
2. A clarifying question (if entity name is ambiguous): "I found multiple [X]. Which one do you mean: [list with disambiguators]?"
3. "I couldn't find [X] in your knowledge graph" (if not found)
4. A list of matching entities/documents (for search queries)
""",
        agent=agent,
    )


def create_analysis_task(
    agent: Agent,
    analysis_type: str = "open_loops",
) -> Task:
    """
    Create a task for analyzing the knowledge graph.
    
    Args:
        agent: The intelligence agent to assign this task to
        analysis_type: Type of analysis ("open_loops", "duplicates", "insights")
    
    Returns:
        CrewAI Task for analysis
    """
    if analysis_type == "open_loops":
        return Task(
            description="""Analyze the knowledge graph for open loops.

Look for:
1. Stale relationships (people not interacted with recently)
2. Stalled projects (no recent activity)
3. Goals that haven't progressed

Use detect_open_loops_tool and supplement with your own analysis.
Prioritize by urgency.
""",
            expected_output="""A list of open loops with:
- Type (relationship, project, goal)
- Entity involved
- Why it needs attention
- Suggested action
- Urgency (1-10)
""",
            agent=agent,
        )
    
    elif analysis_type == "duplicates":
        return Task(
            description="""Find potential duplicate entities in the knowledge graph.

Look for:
1. People with similar names
2. Projects that might be the same
3. Events that might be duplicates

Use find_duplicates_tool and verify with search.
""",
            expected_output="""A list of potential duplicates with:
- Entity 1
- Entity 2
- Similarity score
- Recommendation (merge, keep separate, needs review)
""",
            agent=agent,
        )
    
    else:  # insights
        return Task(
            description="""Generate insights from the knowledge graph.

Analyze:
1. Relationship patterns
2. Project involvement
3. Timeline of activities
4. Key connections

Provide actionable insights for the user.
""",
            expected_output="""A summary of insights with:
- Key patterns observed
- Interesting connections
- Recommendations
""",
            agent=agent,
        )


def create_combined_task(
    ingestion_agent: Agent,
    query_agent: Agent,
    user_input: str,
    intent: dict,
    conversation_id: str | None = None,
    context: list[dict] | None = None,
) -> list[Task]:
    """
    Create tasks for combined ask+add flow.
    
    This handles the case where the user both asks a question
    and provides new information in the same message.
    
    Args:
        ingestion_agent: Agent for extraction
        query_agent: Agent for answering
        user_input: User's input
        intent: Intent analysis result {has_question, has_addition}
        conversation_id: Conversation ID
        context: Conversation context
    
    Returns:
        List of tasks to execute
    """
    tasks = []
    
    if intent.get("has_addition"):
        tasks.append(create_extraction_task(
            ingestion_agent,
            user_input,
            conversation_id,
            context,
        ))
    
    if intent.get("has_question"):
        tasks.append(create_query_task(
            query_agent,
            user_input,
            context,
        ))
    
    return tasks

