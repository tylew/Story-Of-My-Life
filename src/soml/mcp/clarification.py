"""
Clarification Engine - Determines what clarifications are needed for an extraction.

This module analyzes LLM extractions and determines:
- Which clarifications are REQUIRED (must answer or abort)
- Which clarifications are OPTIONAL (nice to have, can skip)
- Generates appropriate questions with context and options

Rules:
- Multiple entity matches with same score → REQUIRED (disambiguation)
- Missing date for event/period → OPTIONAL (can infer or leave blank)
- Ambiguous relationship direction → REQUIRED
- Missing context for new person → OPTIONAL
- Entity type unclear → REQUIRED
"""

from uuid import uuid4

from soml.core.config import get_logger
from soml.core.types import (
    Clarification,
    ClarificationPriority,
    ClarificationRequest,
    ConversationState,
)
from soml.mcp.resolution import EntityResolver

logger = get_logger("mcp.clarification")


class ClarificationEngine:
    """
    Analyzes extractions and generates needed clarifications.
    
    The engine takes LLM extraction output and determines what
    additional information is needed from the user before proposals
    can be generated.
    """
    
    def __init__(self):
        """Initialize the clarification engine."""
        self._resolver = EntityResolver()
    
    def analyze(
        self,
        extraction: dict,
        conversation_id: str,
        context: list[dict] | None = None,
    ) -> ClarificationRequest | None:
        """
        Analyze extraction and return needed clarifications.
        
        Args:
            extraction: The LLM extraction result containing:
                - entities: list of extracted entities
                - relationships: list of proposed relationships
                - document_updates: list of document updates
            conversation_id: Current conversation ID
            context: Optional conversation context (previous messages)
        
        Returns:
            ClarificationRequest if clarifications needed, None otherwise
        """
        clarifications: list[Clarification] = []
        
        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])
        
        # Check for entity ambiguity
        for entity in entities:
            entity_clarifications = self._check_entity_ambiguity(entity)
            clarifications.extend(entity_clarifications)
        
        # Check for relationship clarity
        for rel in relationships:
            rel_clarifications = self._check_relationship_clarity(rel, entities)
            clarifications.extend(rel_clarifications)
        
        # Check for missing dates on events/periods
        for entity in entities:
            date_clarifications = self._check_date_requirements(entity)
            clarifications.extend(date_clarifications)
        
        # Check for entity type clarity
        for entity in entities:
            type_clarifications = self._check_entity_type_clarity(entity)
            clarifications.extend(type_clarifications)
        
        if not clarifications:
            return None
        
        return ClarificationRequest(
            conversation_id=conversation_id,
            state=ConversationState.NEEDS_CLARIFICATION,
            clarifications=clarifications,
            partial_extraction=extraction,
            message=self._generate_message(clarifications),
        )
    
    def _check_entity_ambiguity(self, entity: dict) -> list[Clarification]:
        """
        Check if an entity matches multiple existing entities.
        
        If there are multiple equally-scored matches, the user needs
        to disambiguate which one they mean.
        """
        clarifications = []
        
        name = entity.get("name", "")
        entity_type = entity.get("type", "")
        
        if not name:
            return []
        
        # Try to resolve against existing entities
        result = self._resolver.resolve(name, entity_type or None)
        
        # If multiple candidates with similar scores, ask for disambiguation
        if result.candidates and len(result.candidates) > 1:
            # Check if top candidates have similar scores
            top_score = result.candidates[0].get("match_score", 0)
            close_matches = [
                c for c in result.candidates
                if c.get("match_score", 0) >= top_score - 0.1
            ]
            
            if len(close_matches) > 1:
                options = [
                    f"{c['name']} ({c['type']})" + (f" - {c.get('context', '')}" if c.get('context') else "")
                    for c in close_matches
                ]
                options.append("Create new entity")
                
                clarifications.append(Clarification(
                    id=str(uuid4()),
                    question=f"Which '{name}' do you mean?",
                    priority=ClarificationPriority.REQUIRED,
                    options=options,
                    context=f"I found multiple entities that could match '{name}'.",
                ))
        
        return clarifications
    
    def _check_relationship_clarity(
        self,
        relationship: dict,
        entities: list[dict],
    ) -> list[Clarification]:
        """
        Check if a relationship needs clarification.
        
        E.g., if direction is ambiguous or relationship type is unclear.
        """
        clarifications = []
        
        source = relationship.get("source", "")
        target = relationship.get("target", "")
        rel_type = relationship.get("type", "")
        
        # Check for bidirectional ambiguity in certain relationship types
        symmetric_types = ["knows", "friends", "colleagues", "siblings", "partners"]
        directional_types = ["mentor", "reports_to", "parent", "child"]
        
        if rel_type.lower() in directional_types and not relationship.get("direction_confirmed"):
            # For directional relationships, confirm direction
            clarifications.append(Clarification(
                id=str(uuid4()),
                question=f"Who is the {rel_type} in the relationship between {source} and {target}?",
                priority=ClarificationPriority.REQUIRED,
                options=[
                    f"{source} is the {rel_type}",
                    f"{target} is the {rel_type}",
                ],
                context=f"This relationship type has a direction that matters.",
            ))
        
        return clarifications
    
    def _check_date_requirements(self, entity: dict) -> list[Clarification]:
        """
        Check if an event or period is missing date information.
        
        Missing dates for events/periods are OPTIONAL clarifications
        since the system can proceed without them.
        """
        clarifications = []
        
        entity_type = entity.get("type", "").lower()
        
        if entity_type == "event":
            if not entity.get("on_date") and not entity.get("start_date"):
                clarifications.append(Clarification(
                    id=str(uuid4()),
                    question=f"When did '{entity.get('name', 'this event')}' happen?",
                    priority=ClarificationPriority.OPTIONAL,
                    context="Providing a date helps organize the timeline.",
                    default_value="Unknown date",
                ))
        
        elif entity_type == "period":
            has_start = entity.get("start_date")
            has_end = entity.get("end_date")
            
            if not has_start and not has_end:
                name = entity.get("name", "this period")
                clarifications.append(Clarification(
                    id=str(uuid4()),
                    question=f"When does '{name}' start and/or end?",
                    priority=ClarificationPriority.OPTIONAL,
                    context="Dates help track this period on the timeline. You can specify start only, end only, or both.",
                    default_value="Dates pending",
                ))
        
        return clarifications
    
    def _check_entity_type_clarity(self, entity: dict) -> list[Clarification]:
        """
        Check if an entity's type is unclear or ambiguous.
        
        If the LLM couldn't determine the entity type with confidence,
        ask the user.
        """
        clarifications = []
        
        entity_type = entity.get("type", "").lower()
        confidence = entity.get("confidence", 1.0)
        name = entity.get("name", "")
        
        # If entity type is missing or confidence is low, ask
        if not entity_type:
            clarifications.append(Clarification(
                id=str(uuid4()),
                question=f"What type of entity is '{name}'?",
                priority=ClarificationPriority.REQUIRED,
                options=["Person", "Project", "Goal", "Event", "Period"],
                context="I need to know what kind of entity this is.",
            ))
        elif confidence < 0.5:
            clarifications.append(Clarification(
                id=str(uuid4()),
                question=f"Is '{name}' a {entity_type}?",
                priority=ClarificationPriority.OPTIONAL,
                options=["Yes", "No - it's a Person", "No - it's a Project", "No - it's a Goal", "No - it's an Event", "No - it's a Period"],
                context=f"I'm not very confident that this is a {entity_type}.",
                default_value="Yes",
            ))
        
        return clarifications
    
    def _generate_message(self, clarifications: list[Clarification]) -> str:
        """
        Generate a friendly message explaining the clarifications.
        """
        required = [c for c in clarifications if c.priority == ClarificationPriority.REQUIRED]
        optional = [c for c in clarifications if c.priority == ClarificationPriority.OPTIONAL]
        
        parts = []
        
        if required:
            parts.append(f"I need {len(required)} answer{'s' if len(required) > 1 else ''} before I can proceed.")
        
        if optional:
            if required:
                parts.append(f"There {'are' if len(optional) > 1 else 'is'} also {len(optional)} optional question{'s' if len(optional) > 1 else ''} that would help me give you better results.")
            else:
                parts.append(f"I have {len(optional)} optional question{'s' if len(optional) > 1 else ''} that would help me give you better results. Feel free to skip if you prefer.")
        
        return " ".join(parts)
    
    def apply_answers(
        self,
        extraction: dict,
        clarifications: list[Clarification],
    ) -> dict:
        """
        Apply clarification answers to the extraction.
        
        This modifies the extraction based on the user's answers
        to the clarification questions.
        
        Args:
            extraction: Original extraction
            clarifications: Clarifications with answers filled in
        
        Returns:
            Modified extraction with answers applied
        """
        # Create a copy to avoid mutating the original
        updated = {
            "entities": list(extraction.get("entities", [])),
            "relationships": list(extraction.get("relationships", [])),
            "document_updates": list(extraction.get("document_updates", [])),
        }
        
        for clarification in clarifications:
            if clarification.skipped:
                # Use default value if available
                if clarification.default_value:
                    self._apply_default(updated, clarification)
            elif clarification.answer:
                self._apply_answer(updated, clarification)
        
        return updated
    
    def _apply_answer(self, extraction: dict, clarification: Clarification) -> None:
        """
        Apply a single clarification answer to the extraction.
        """
        answer = clarification.answer
        question = clarification.question
        
        # Handle entity disambiguation
        if "Which" in question and "do you mean?" in question:
            # Extract entity name from question
            entity_name = question.replace("Which '", "").replace("' do you mean?", "")
            
            if "Create new entity" in answer:
                # Keep as-is, it's a new entity
                pass
            else:
                # User selected an existing entity
                # Mark the entity to use the selected one
                for entity in extraction.get("entities", []):
                    if entity.get("name", "").lower() == entity_name.lower():
                        # Parse the selected entity info
                        entity["selected_existing"] = answer
                        break
        
        # Handle entity type selection
        elif "What type of entity is" in question:
            entity_name = question.replace("What type of entity is '", "").replace("'?", "")
            for entity in extraction.get("entities", []):
                if entity.get("name", "").lower() == entity_name.lower():
                    entity["type"] = answer.lower()
                    break
        
        # Handle "Is X a Y?" type questions
        elif "Is '" in question and "' a " in question:
            if answer == "Yes":
                # Keep current type
                pass
            elif answer.startswith("No - it's a "):
                new_type = answer.replace("No - it's a ", "").lower()
                # Find and update the entity
                entity_name = question.split("'")[1]
                for entity in extraction.get("entities", []):
                    if entity.get("name", "").lower() == entity_name.lower():
                        entity["type"] = new_type
                        break
        
        # Handle relationship direction
        elif "Who is the" in question and "in the relationship" in question:
            # Parse out the relationship type and entities
            parts = question.split(" ")
            # Update the relationship source/target based on answer
            pass  # Complex parsing needed
        
        # Handle date questions
        elif "When did" in question or "When does" in question:
            # Try to parse date from answer and update entity
            for entity in extraction.get("entities", []):
                if entity.get("name", "") in question:
                    if "event" in entity.get("type", "").lower():
                        entity["on_date"] = answer
                    elif "period" in entity.get("type", "").lower():
                        entity["start_date"] = answer
                    break
    
    def _apply_default(self, extraction: dict, clarification: Clarification) -> None:
        """
        Apply a default value when a clarification is skipped.
        """
        # For now, just log that we're using the default
        logger.debug(f"Using default value '{clarification.default_value}' for skipped clarification")


# Singleton instance
_engine: ClarificationEngine | None = None


def get_clarification_engine() -> ClarificationEngine:
    """Get the singleton clarification engine instance."""
    global _engine
    if _engine is None:
        _engine = ClarificationEngine()
    return _engine

