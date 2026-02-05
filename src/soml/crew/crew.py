"""
SOMLCrew - Main CrewAI orchestrator for Story of My Life.

This is the primary interface for all agent operations.
It creates and manages agents, assigns tasks, and handles results.
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from crewai import Crew, Process

from soml.core.config import get_logger
from soml.crew.agents import (
    create_ingestion_agent,
    create_query_agent,
    create_intelligence_agent,
)
from soml.crew.tasks import (
    create_extraction_task,
    create_query_task,
    create_analysis_task,
    create_combined_task,
)
from soml.storage.conversations import ConversationStore

logger = get_logger("crew.crew")


@dataclass
class IngestResult:
    """Result of ingestion operation."""
    
    success: bool
    entities: list[dict]
    relationships: list[dict]
    needs_confirmation: list[dict]
    message: str
    raw_output: str | None = None


@dataclass
class QueryResult:
    """Result of query operation."""
    
    success: bool
    answer: str
    sources: list[dict]  # List of {id, name, type} for entities/documents referenced
    raw_output: str | None = None
    
    @staticmethod
    def extract_entity_refs(text: str) -> list[dict]:
        """
        Extract entity references from agent output.
        
        Looks for patterns like:
        - [entity:uuid:name:type]
        - [document:uuid:name]
        """
        import re
        refs = []
        seen_ids = set()
        
        # Pattern: [entity:uuid:name:type]
        entity_pattern = r'\[entity:([a-f0-9-]+):([^:]+):([^\]]+)\]'
        for match in re.finditer(entity_pattern, text):
            entity_id = match.group(1)
            if entity_id not in seen_ids:
                refs.append({
                    "id": entity_id,
                    "name": match.group(2),
                    "type": match.group(3),
                })
                seen_ids.add(entity_id)
        
        # Pattern: [document:uuid:name]
        doc_pattern = r'\[document:([a-f0-9-]+):([^\]]+)\]'
        for match in re.finditer(doc_pattern, text):
            doc_id = match.group(1)
            if doc_id not in seen_ids:
                refs.append({
                    "id": doc_id,
                    "name": match.group(2),
                    "type": "document",
                })
                seen_ids.add(doc_id)
        
        return refs


@dataclass
class AnalysisResult:
    """Result of analysis operation."""
    
    success: bool
    loops: list[dict]
    insights: list[str]
    raw_output: str | None = None


class SOMLCrew:
    """
    Main orchestrator for SOML operations.
    
    Provides high-level methods for:
    - ingest(text): Extract and store entities/relationships
    - query(question): Answer questions about the knowledge graph
    - analyze(): Detect patterns and open loops
    - process(text, conv_id): Combined flow with context
    """
    
    def __init__(self):
        """Initialize the crew with agents."""
        self.conv_store = ConversationStore()
        self._ingestion_agent = None
        self._query_agent = None
        self._intelligence_agent = None
    
    @property
    def ingestion_agent(self):
        """Lazy load ingestion agent."""
        if self._ingestion_agent is None:
            self._ingestion_agent = create_ingestion_agent()
        return self._ingestion_agent
    
    @property
    def query_agent(self):
        """Lazy load query agent."""
        if self._query_agent is None:
            self._query_agent = create_query_agent()
        return self._query_agent
    
    @property
    def intelligence_agent(self):
        """Lazy load intelligence agent."""
        if self._intelligence_agent is None:
            self._intelligence_agent = create_intelligence_agent()
        return self._intelligence_agent
    
    def ingest(
        self,
        text: str,
        conversation_id: str | None = None,
        context: list[dict] | None = None,
    ) -> IngestResult:
        """
        Ingest text and extract entities/relationships.
        
        Args:
            text: User input text
            conversation_id: Optional conversation ID for context
            context: Optional list of previous messages
        
        Returns:
            IngestResult with extracted entities and relationships
        """
        try:
            # Create extraction task
            task = create_extraction_task(
                self.ingestion_agent,
                text,
                conversation_id,
                context,
            )
            
            # Create and run crew
            crew = Crew(
                agents=[self.ingestion_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            result = crew.kickoff()
            
            # Parse result
            try:
                parsed = json.loads(str(result))
            except json.JSONDecodeError:
                parsed = {"raw": str(result)}
            
            return IngestResult(
                success=True,
                entities=parsed.get("entities", []),
                relationships=parsed.get("relationships", []),
                needs_confirmation=parsed.get("needs_confirmation", []),
                message="Extraction complete",
                raw_output=str(result),
            )
            
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return IngestResult(
                success=False,
                entities=[],
                relationships=[],
                needs_confirmation=[],
                message=f"Error: {str(e)}",
            )
    
    def query(
        self,
        question: str,
        conversation_id: str | None = None,
        context: list[dict] | None = None,
    ) -> QueryResult:
        """
        Answer a question using the knowledge graph.
        
        Args:
            question: The question to answer
            conversation_id: Optional conversation ID
            context: Optional conversation context
        
        Returns:
            QueryResult with answer and sources
        """
        try:
            # Create query task
            task = create_query_task(
                self.query_agent,
                question,
                context,
            )
            
            # Create and run crew
            crew = Crew(
                agents=[self.query_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            result = crew.kickoff()
            raw_output = str(result)
            
            # Extract entity references from the output
            sources = QueryResult.extract_entity_refs(raw_output)
            
            # Clean the answer by removing entity and document reference markers
            import re
            clean_answer = re.sub(r'\[entity:[a-f0-9-]+:[^:]+:[^\]]+\]', '', raw_output)
            clean_answer = re.sub(r'\[document:[a-f0-9-]+:[^\]]+\]', '', clean_answer)
            # Clean up extra whitespace
            clean_answer = re.sub(r'\s+', ' ', clean_answer).strip()
            
            return QueryResult(
                success=True,
                answer=clean_answer,
                sources=sources,
                raw_output=raw_output,
            )
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return QueryResult(
                success=False,
                answer=f"I couldn't answer that question: {str(e)}",
                sources=[],
            )
    
    def analyze(
        self,
        analysis_type: str = "open_loops",
    ) -> AnalysisResult:
        """
        Analyze the knowledge graph.
        
        Args:
            analysis_type: "open_loops", "duplicates", or "insights"
        
        Returns:
            AnalysisResult with findings
        """
        try:
            # Create analysis task
            task = create_analysis_task(
                self.intelligence_agent,
                analysis_type,
            )
            
            # Create and run crew
            crew = Crew(
                agents=[self.intelligence_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            
            result = crew.kickoff()
            
            # Parse result
            try:
                parsed = json.loads(str(result))
                loops = parsed if isinstance(parsed, list) else parsed.get("loops", [])
            except json.JSONDecodeError:
                loops = []
            
            return AnalysisResult(
                success=True,
                loops=loops,
                insights=[],
                raw_output=str(result),
            )
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return AnalysisResult(
                success=False,
                loops=[],
                insights=[f"Error: {str(e)}"],
            )
    
    async def parse_only(
        self,
        text: str,
        conversation_id: str | None = None,
    ) -> dict:
        """
        Parse user input and extract entities/relationships WITHOUT executing.
        
        This is used by the proposal system to get parsed data that will
        then be matched against existing entities and presented to the user.
        
        Args:
            text: User input
            conversation_id: Conversation ID for context
        
        Returns:
            Dict with intent, entities, and relationships (not created yet)
        """
        # Get conversation context
        context = []
        if conversation_id:
            messages = self.conv_store.get_messages(conversation_id, limit=10)
            context = [{"role": m["role"], "content": m["content"]} for m in messages]
        
        # Analyze intent
        intent = await self._analyze_intent(text, context)
        
        # Determine intent type for routing
        if intent.get("has_question") and not intent.get("has_addition"):
            intent["type"] = "query"
        elif intent.get("has_addition") and not intent.get("has_question"):
            intent["type"] = "addition"
        else:
            intent["type"] = "mixed"
        
        result = {
            "conversation_id": conversation_id,
            "intent": intent,
            "entities": [],
            "relationships": [],
            "document_updates": [],
        }
        
        # If it's a question only, return early - don't extract entities
        if intent.get("type") == "query":
            return result
        
        # Extract entities and relationships using LLM
        parsed = await self._extract_entities_and_relationships(text, context)
        result["entities"] = parsed.get("entities", [])
        result["document_updates"] = parsed.get("document_updates", [])
        result["relationships"] = parsed.get("relationships", [])
        result["message"] = parsed.get("message", "")
        
        return result
    
    async def _extract_entities_and_relationships(
        self,
        text: str,
        context: list[dict] | None = None,
    ) -> dict:
        """
        Extract entities and relationships from text using LLM.
        
        This does NOT create anything - just parses the text.
        """
        from soml.core.llm import call_llm
        
        context_str = ""
        if context:
            recent = context[-5:]
            context_str = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
        
        today = date.today().isoformat()
        
        prompt = f"""Extract entities, relationships, and information updates from the user's message.
        
Today's date: {today}

ENTITY TYPES:
- person: People (e.g., "my dad", "John", "Alice")  
- project: User's OWN projects (NOT external companies like Google, Apple)
- goal: Personal objectives
- event: ONLY for schedulable calendar events (meetings, birthdays, appointments)
- period: Life phases or time spans - NEW JOBS, college years, relationships, living situations

CRITICAL: PERIODS vs EVENTS
- "Starting a new job at X" → PERIOD (not event) - a job is a phase of life
- "Working at X", "Position at X" → PERIOD
- "Moving to a new city" → PERIOD  
- "Starting college" → PERIOD
- "Meeting with X at 3pm" → EVENT (specific scheduled moment)
- "Birthday party on Saturday" → EVENT

TEXT NORMALIZATION:
- Always capitalize proper nouns: "brightfield" → "Brightfield"
- Company names: "brightfield ai" → "Brightfield AI"
- Use formal names in entities: "my job at brightfield" → "Position at Brightfield AI"

CRITICAL RULES:
1. External companies (Google, Apple, Brightfield) are NOT separate entities - they appear IN period names
2. Status updates about existing entities go in document_updates, NOT as new entities
3. "Raised funding", "launched product" are document_updates, NOT event entities

EXAMPLES:
- "Starting a new job feb 17 at brightfield ai" → entities: [{{"name": "Position at Brightfield AI", "type": "period", "context": "Starting Feb 17"}}]
- "I'm joining Google next month" → entities: [{{"name": "Position at Google", "type": "period", "context": "Starting next month"}}]  
- "Alice and Bob know each other" → entities: [Alice (person), Bob (person)], relationship: knows
- "Project Astra raised 200M yesterday" → document_updates: [{{"entity_name": "Project Astra", "content": "Raised $200M funding"}}]
- "Meeting with John tomorrow at 3pm" → entities: [John (person), Meeting with John (event)]

Recent conversation:
{context_str}

User message: {text}

Return JSON (ALL fields required, use empty arrays [] if none):
{{
    "entities": [
        {{
            "name": "Properly Capitalized Name", 
            "type": "person|project|goal|event|period", 
            "context": "Brief description",
            "start_date": "YYYY-MM-DD or null",
            "end_date": "YYYY-MM-DD or null",
            "on_date": "YYYY-MM-DD or null (for events only)"
        }}
    ],
    "relationships": [
        {{"source_name": "...", "target_name": "...", "type": "...", "reason": "..."}}
    ],
    "document_updates": [
        {{"entity_name": "...", "content": "The actual update/news to record"}}
    ],
    "message": "Brief summary"
}}

DATE EXTRACTION RULES:
- For periods: Extract start_date and end_date as YYYY-MM-DD (use today's date: {today} to calculate relative dates)
- "Starting feb 17" → start_date: "{date.today().year}-02-17" (assume current year unless specified)
- "From May 2024 to Jan 28" → start_date: "2024-05-01", end_date: "{date.today().year}-01-28"
- "Next month" → calculate actual date from today
- For events: Use on_date field instead of start_date
- Use null for unknown dates (NOT an empty string)

REMEMBER: New jobs, positions, life phases are PERIODS, not events!"""

        response = await call_llm(prompt)
        
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                parsed = json.loads(json_match.group())
                return parsed
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
        
        return {"entities": [], "relationships": [], "document_updates": [], "message": "Could not parse extraction"}

    async def process(
        self,
        text: str,
        conversation_id: str | None = None,
    ) -> dict:
        """
        Process user input with full context management.
        
        This is the main entry point for conversational interactions.
        It handles:
        - Intent analysis (question vs addition)
        - Conversation context retrieval
        - Entity resolution using context
        - Combined ask+add flows
        
        Args:
            text: User input
            conversation_id: Conversation ID (created if None)
        
        Returns:
            Dict with results and any confirmation needed
        """
        # Get or create conversation
        conv_id = self.conv_store.get_or_create_conversation(conversation_id)
        
        # Get conversation history
        messages = self.conv_store.get_messages(conv_id, limit=10)
        context = [{"role": m["role"], "content": m["content"]} for m in messages]
        
        # Add user message to conversation
        self.conv_store.add_message(conv_id, "user", text)
        
        # Analyze intent
        intent = await self._analyze_intent(text, context)
        
        # Process based on intent
        result = {
            "conversation_id": conv_id,
            "intent": intent,
        }
        
        if intent.get("has_addition"):
            ingest_result = self.ingest(text, conv_id, context)
            result["extraction"] = {
                "success": ingest_result.success,
                "entities": ingest_result.entities,
                "relationships": ingest_result.relationships,
                "needs_confirmation": ingest_result.needs_confirmation,
            }
            
            if ingest_result.needs_confirmation:
                result["requires_confirmation"] = True
        
        if intent.get("has_question"):
            query_result = self.query(text, conv_id, context)
            result["answer"] = query_result.answer
            result["sources"] = query_result.sources
        
        # Add assistant response to conversation
        if result.get("answer"):
            self.conv_store.add_message(conv_id, "assistant", result["answer"])
        elif result.get("extraction", {}).get("success"):
            entities = result["extraction"]["entities"]
            msg = f"Added {len(entities)} entities to your knowledge graph."
            self.conv_store.add_message(conv_id, "assistant", msg)
            result["message"] = msg
        
        return result
    
    async def _analyze_intent(
        self,
        text: str,
        context: list[dict] | None = None,
    ) -> dict:
        """
        Analyze the intent of user input.
        
        Returns:
            Dict with has_question and has_addition booleans
        """
        from soml.core.llm import call_llm
        
        context_str = ""
        if context:
            context_str = "\n".join([
                f"{m['role']}: {m['content']}" 
                for m in context[-5:]
            ])
        
        prompt = f"""
        Analyze this message and determine the user's intent.
        
        Recent conversation:
        {context_str}
        
        Current message: "{text}"
        
        Respond with JSON:
        {{
            "has_question": true/false,
            "has_addition": true/false,
            "question_summary": "what they're asking" or null,
            "addition_summary": "what they want to add" or null
        }}
        
        Guidelines:
        - has_question: Is the user asking for information, querying, or wanting to retrieve data?
        - has_addition: Is the user providing new information to store?
        
        QUESTION phrases (has_question: true):
        - "What do we know about X"
        - "Tell me about X"
        - "Can you tell me about X"
        - "Who is X"
        - "What happened with X"
        - "Give me info on X"
        - "Can you tell me about Frank's wife"
        - "I forget which person has X, please find them"
        - "Locate the document about X"
        - Any question asking to retrieve/recall information
        
        ADDITION phrases (has_addition: true):
        - "X is my friend/coworker/etc"
        - "I met X"
        - "X works at Y"
        - "X invested in Y"
        - Statements providing new facts
        
        Examples:
        - "Who is John?" → has_question: true, has_addition: false
        - "What do we know about Frank?" → has_question: true, has_addition: false
        - "Tell me about Alice" → has_question: true, has_addition: false
        - "Can you tell me about Frank's wife" → has_question: true, has_addition: false
        - "I forget which person has a wife I made notes on" → has_question: true, has_addition: false
        - "John is my coworker" → has_question: false, has_addition: true  
        - "My dad Craig is investing in ATitan. What do we know about the deal?" → both true
        """
        
        try:
            response = await call_llm(prompt, response_format="json")
            if isinstance(response, dict):
                return response
        except Exception as e:
            logger.warning(f"Intent analysis failed: {e}")
        
        # Fallback: improved heuristics
        text_lower = text.lower().strip()
        
        # Question patterns
        question_patterns = [
            '?',  # Has question mark
            'who ', 'who\'s', 'whos',
            'what ', 'what\'s', 'whats',
            'when ', 'when\'s',
            'where ', 'where\'s',
            'why ', 'why\'s',
            'how ', 'how\'s',
            'tell me about',
            'tell me what',
            'can you tell me',
            'could you tell me',
            'what do we know',
            'what does',
            'do we know',
            'do you know',
            'give me info',
            'show me',
            'list ',
            'find ',
            'locate ',
            'search for',
            'look up',
            'i forget', 'i forgot',  # User is asking to find something
            'which person', 'which project', 'which one',
            '\'s wife', '\'s husband', '\'s friend',  # Possessive lookups
        ]
        
        # Addition patterns  
        addition_patterns = [
            ' is my ', ' are my ',
            'i met ', 'i\'ve met',
            'we discussed',
            ' works at ', ' worked at ',
            ' invested ', ' invests ',
            ' knows ', ' know ',
            ' started ', ' starts ',
            ' joined ',
            ' is a ', ' is an ',
            ' hired ', ' fired ',
            ' raised ', ' launched ',
        ]
        
        has_question = any(q in text_lower for q in question_patterns)
        has_addition = any(a in text_lower for a in addition_patterns)
        
        # If nothing matched, and it looks like a statement about someone, default to question
        # (user is likely asking about that person)
        if not has_question and not has_addition:
            # Check if it's just a name or simple reference
            words = text_lower.split()
            if len(words) <= 5 and not any(verb in text_lower for verb in ['is', 'was', 'are', 'were', 'has', 'have']):
                has_question = True  # Treat short phrases as queries
        
        return {
            "has_question": has_question,
            "has_addition": has_addition,
        }


# Singleton instance
_crew: SOMLCrew | None = None


def get_crew() -> SOMLCrew:
    """Get the singleton crew instance."""
    global _crew
    if _crew is None:
        _crew = SOMLCrew()
    return _crew

