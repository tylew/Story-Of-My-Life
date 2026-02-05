"""
Proposal Generation - Creates proposals for user review before any changes.

This module implements the proposal flow:
1. Parse input → Extract entity mentions
2. Find candidates → Match against existing entities
3. Generate proposals → Entity resolutions + relationships + documents
4. User review → Accept/Edit/Reject each proposal
5. Execute → Only approved proposals get applied
6. Return IDs → Feed created IDs back to LLM for context
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from soml.core.config import get_logger
from soml.mcp.resolution import EntityResolver
from soml.storage.registry import RegistryStore
from soml.storage.markdown import MarkdownStore

logger = get_logger("mcp.proposals")


@dataclass
class EntityCandidate:
    """A candidate for entity resolution."""
    
    id: str | None
    """Entity ID (None for 'create new' option)."""
    
    name: str
    """Entity name."""
    
    type: str
    """Entity type."""
    
    context: str | None = None
    """Disambiguating context."""
    
    match_score: float = 0.0
    """How well this matches the mention (0-1)."""
    
    match_reason: str | None = None
    """Why this is a candidate."""
    
    is_create_new: bool = False
    """Whether this is the 'create new' option."""


@dataclass
class EntityProposal:
    """A proposal for handling an entity mention."""
    
    proposal_id: str
    """Unique ID for this proposal."""
    
    mention: str
    """The original mention from user input."""
    
    inferred_type: str
    """Inferred entity type."""
    
    inferred_context: str | None
    """Inferred context from user input."""
    
    candidates: list[EntityCandidate]
    """Possible matches including 'create new' option."""
    
    selected_candidate_id: str | None = None
    """User's selection (None = pending)."""
    
    user_notes: str | None = None
    """Optional notes/description from user."""


@dataclass
class RelationshipProposal:
    """A proposal for a relationship change."""
    
    proposal_id: str
    """Unique ID for this proposal."""
    
    action: Literal["add", "replace", "remove"]
    """Type of change."""
    
    source_mention: str
    """Source entity mention (resolved after entity proposals)."""
    
    target_mention: str
    """Target entity mention (resolved after entity proposals)."""
    
    relationship_type: str
    """Relationship type."""
    
    old_type: str | None = None
    """Existing type (for replace/remove)."""
    
    reason: str | None = None
    """LLM's reasoning."""
    
    approved: bool | None = None
    """User's decision (None = pending)."""
    
    source_entity_id: str | None = None
    """Resolved source ID (after entity selection)."""
    
    target_entity_id: str | None = None
    """Resolved target ID (after entity selection)."""


@dataclass
class DocumentProposal:
    """A proposal for document changes."""
    
    proposal_id: str
    """Unique ID for this proposal."""
    
    action: Literal["create", "append", "update"]
    """Type of change."""
    
    entity_mention: str
    """Entity this document is for."""
    
    title: str | None = None
    """Document title (for create)."""
    
    content: str | None = None
    """Content to add."""
    
    approved: bool | None = None
    """User's decision (None = pending)."""


@dataclass
class ProposalSet:
    """A complete set of proposals for user review."""
    
    proposal_set_id: str
    """Unique ID for this proposal set."""
    
    conversation_id: str | None
    """Associated conversation."""
    
    original_input: str
    """The user's original input."""
    
    entity_proposals: list[EntityProposal] = field(default_factory=list)
    """Entity resolution proposals."""
    
    relationship_proposals: list[RelationshipProposal] = field(default_factory=list)
    """Relationship change proposals."""
    
    document_proposals: list[DocumentProposal] = field(default_factory=list)
    """Document change proposals."""
    
    created_at: datetime = field(default_factory=datetime.now)
    """When proposals were generated."""
    
    status: Literal["pending", "partial", "approved", "executed", "rejected"] = "pending"
    """Overall status."""


class ProposalGenerator:
    """
    Generates proposals from parsed input without executing any changes.
    """
    
    def __init__(self):
        self.resolver = EntityResolver()
        self.registry = RegistryStore()
        self.md_store = MarkdownStore()
    
    def generate_proposals(
        self,
        parsed_entities: list[dict],
        parsed_relationships: list[dict],
        user_input: str,
        conversation_id: str | None = None,
        document_updates: list[dict] | None = None,
    ) -> ProposalSet:
        """
        Generate a complete proposal set from parsed input.
        
        Args:
            parsed_entities: List of {name, type, context} dicts from LLM extraction
            parsed_relationships: List of {source_name, target_name, type} dicts
            user_input: Original user input
            conversation_id: Conversation ID for context
            document_updates: List of {entity_name, content, reason} for appending to docs
        
        Returns:
            ProposalSet ready for user review
        """
        proposal_set = ProposalSet(
            proposal_set_id=str(uuid4()),
            conversation_id=conversation_id,
            original_input=user_input,
        )
        
        # Generate entity proposals
        for entity_data in parsed_entities:
            entity_proposal = self._generate_entity_proposal(
                name=entity_data.get("name", ""),
                entity_type=entity_data.get("type", "person"),
                context=entity_data.get("context"),
                conversation_id=conversation_id,
            )
            proposal_set.entity_proposals.append(entity_proposal)
        
        # Generate relationship proposals
        for rel_data in parsed_relationships:
            rel_proposal = self._generate_relationship_proposal(
                source_name=rel_data.get("source_name", ""),
                target_name=rel_data.get("target_name", ""),
                rel_type=rel_data.get("type", "related_to"),
                reason=rel_data.get("reason"),
                entity_proposals=proposal_set.entity_proposals,
            )
            proposal_set.relationship_proposals.append(rel_proposal)
        
        # Generate document update proposals from explicit updates
        for doc_update in (document_updates or []):
            doc_proposal = self._generate_document_proposal(
                entity_name=doc_update.get("entity_name", ""),
                content=doc_update.get("content", ""),
                reason=doc_update.get("reason"),
                entity_proposals=proposal_set.entity_proposals,
            )
            if doc_proposal:
                proposal_set.document_proposals.append(doc_proposal)
        
        # Auto-generate document updates for existing entities with new related info
        self._generate_auto_document_updates(
            proposal_set=proposal_set,
            user_input=user_input,
        )
        
        return proposal_set
    
    def _generate_auto_document_updates(
        self,
        proposal_set: ProposalSet,
        user_input: str,
    ) -> None:
        """
        Auto-generate document updates when:
        1. Linking to an existing entity AND
        2. There are new related entities/events being created
        
        This ensures information isn't lost when we just "link" to existing.
        """
        # Find entities that are linking to existing (high-confidence match)
        existing_entities = []
        new_entities = []
        
        for ep in proposal_set.entity_proposals:
            if ep.selected_candidate_id:
                # Has an auto-selected existing entity
                existing_entities.append(ep)
            elif not any(c.id for c in ep.candidates if not c.is_create_new and c.match_score >= 0.95):
                # No high-confidence match, will be created new
                new_entities.append(ep)
        
        # For each existing entity that has related new entities, create a document update
        for existing_ep in existing_entities:
            # Find relationships involving this entity
            related_new = []
            for rp in proposal_set.relationship_proposals:
                if rp.source_mention.lower() == existing_ep.mention.lower():
                    # Find what it's related to
                    target = next((e for e in new_entities if e.mention.lower() == rp.target_mention.lower()), None)
                    if target:
                        related_new.append((rp, target))
                elif rp.target_mention.lower() == existing_ep.mention.lower():
                    source = next((e for e in new_entities if e.mention.lower() == rp.source_mention.lower()), None)
                    if source:
                        related_new.append((rp, source))
            
            if related_new:
                # Create a document update summarizing the new info
                update_parts = []
                for rel, new_entity in related_new:
                    context = new_entity.inferred_context or ""
                    update_parts.append(f"- {new_entity.mention}: {context}" if context else f"- {new_entity.mention}")
                
                if update_parts:
                    doc_proposal = DocumentProposal(
                        proposal_id=str(uuid4()),
                        action="append",
                        entity_mention=existing_ep.mention,
                        title=None,
                        content="New developments:\n" + "\n".join(update_parts),
                        approved=True,
                    )
                    proposal_set.document_proposals.append(doc_proposal)
    
    def _generate_entity_proposal(
        self,
        name: str,
        entity_type: str,
        context: str | None,
        conversation_id: str | None,
    ) -> EntityProposal:
        """Generate a proposal for a single entity mention."""
        
        proposal = EntityProposal(
            proposal_id=str(uuid4()),
            mention=name,
            inferred_type=entity_type,
            inferred_context=context,
            candidates=[],
        )
        
        # Find potential matches
        candidates = self._find_entity_candidates(name, entity_type, context, conversation_id)
        proposal.candidates = candidates
        
        # Auto-select if there's a high-confidence exact match
        for candidate in candidates:
            if not candidate.is_create_new and candidate.match_score >= 0.95:
                proposal.selected_candidate_id = candidate.id
                break
        
        return proposal
    
    def _find_entity_candidates(
        self,
        name: str,
        entity_type: str,
        context: str | None,
        conversation_id: str | None,
    ) -> list[EntityCandidate]:
        """Find all potential matches for an entity mention."""
        
        candidates = []
        
        # Search for exact name matches
        exact_matches = self.registry.search(name, limit=10)
        for match in exact_matches:
            if match.get("type", "").lower() == entity_type.lower():
                score = 1.0 if match.get("name", "").lower() == name.lower() else 0.8
                candidates.append(EntityCandidate(
                    id=match.get("id"),
                    name=match.get("name", ""),
                    type=match.get("type", ""),
                    context=match.get("disambiguator") or match.get("context"),
                    match_score=score,
                    match_reason="Exact name match" if score == 1.0 else "Similar name",
                ))
        
        # Search for fuzzy matches
        fuzzy_matches = self.resolver._find_fuzzy(name.lower(), entity_type, context)
        for match in fuzzy_matches:
            if match.get("id") not in [c.id for c in candidates]:
                candidates.append(EntityCandidate(
                    id=match.get("id"),
                    name=match.get("name", ""),
                    type=match.get("type", ""),
                    context=match.get("disambiguator"),
                    match_score=match.get("score", 0.5),
                    match_reason="Fuzzy match",
                ))
        
        # Add context-based matches from conversation
        if conversation_id:
            from soml.storage.conversations import ConversationStore
            conv_store = ConversationStore()
            conv_entities = conv_store.get_entity_context(conversation_id)
            
            for mention, entity_id in conv_entities.items():
                if name.lower() in mention.lower() or mention.lower() in name.lower():
                    entity = self.registry.get(entity_id)
                    if entity and entity.get("id") not in [c.id for c in candidates]:
                        candidates.append(EntityCandidate(
                            id=entity.get("id"),
                            name=entity.get("name", ""),
                            type=entity.get("type", ""),
                            context=entity.get("disambiguator"),
                            match_score=0.9,
                            match_reason="Referenced earlier in conversation",
                        ))
        
        # Sort by score
        candidates.sort(key=lambda c: c.match_score, reverse=True)
        
        # Always add "create new" option at the end
        candidates.append(EntityCandidate(
            id=None,
            name=name,
            type=entity_type,
            context=context,
            match_score=0.0,
            match_reason="Create as new entity",
            is_create_new=True,
        ))
        
        return candidates
    
    def _generate_relationship_proposal(
        self,
        source_name: str,
        target_name: str,
        rel_type: str,
        reason: str | None,
        entity_proposals: list[EntityProposal],
    ) -> RelationshipProposal:
        """Generate a proposal for a relationship."""
        
        proposal = RelationshipProposal(
            proposal_id=str(uuid4()),
            action="add",
            source_mention=source_name,
            target_mention=target_name,
            relationship_type=rel_type,
            reason=reason,
        )
        
        # Check if we need to do a replace instead of add
        # This requires checking existing relationships between the entities
        source_proposal = next((p for p in entity_proposals if p.mention.lower() == source_name.lower()), None)
        target_proposal = next((p for p in entity_proposals if p.mention.lower() == target_name.lower()), None)
        
        if source_proposal and target_proposal:
            # Find if there's already a relationship between high-confidence candidates
            for s_cand in source_proposal.candidates[:1]:  # Check top candidate
                if s_cand.id:
                    for t_cand in target_proposal.candidates[:1]:
                        if t_cand.id:
                            existing = self._check_existing_relationship(s_cand.id, t_cand.id)
                            if existing:
                                proposal.action = "replace"
                                proposal.old_type = existing.get("type")
        
        return proposal
    
    def _check_existing_relationship(self, source_id: str, target_id: str) -> dict | None:
        """Check if a relationship already exists between two entities."""
        from soml.mcp.tools import get_entity_relationships
        
        rels = get_entity_relationships(source_id)
        for rel in rels:
            if rel.get("other_entity_id") == target_id:
                return rel
        return None
    
    def _generate_document_proposal(
        self,
        entity_name: str,
        content: str,
        reason: str | None,
        entity_proposals: list[EntityProposal],
    ) -> DocumentProposal | None:
        """Generate a proposal to update an entity's document."""
        
        if not entity_name or not content:
            return None
        
        # Find the entity proposal this relates to
        entity_proposal = next(
            (p for p in entity_proposals if p.mention.lower() == entity_name.lower()),
            None
        )
        
        # Also try to find existing entity directly
        entity_id = None
        if entity_proposal:
            # Get the top candidate if it's an existing entity
            for candidate in entity_proposal.candidates:
                if candidate.id and not candidate.is_create_new:
                    entity_id = candidate.id
                    break
        else:
            # Search for entity by name
            matches = self.registry.search(entity_name, limit=1)
            if matches:
                entity_id = matches[0].get("id")
        
        return DocumentProposal(
            proposal_id=str(uuid4()),
            action="append",
            entity_mention=entity_name,
            title=None,
            content=content,
            approved=True,  # Default to approved
        )


def proposal_set_to_dict(proposal_set: ProposalSet) -> dict:
    """Convert a ProposalSet to a JSON-serializable dict."""
    return {
        "proposal_set_id": proposal_set.proposal_set_id,
        "conversation_id": proposal_set.conversation_id,
        "original_input": proposal_set.original_input,
        "status": proposal_set.status,
        "entity_proposals": [
            {
                "proposal_id": p.proposal_id,
                "mention": p.mention,
                "inferred_type": p.inferred_type,
                "inferred_context": p.inferred_context,
                "selected_candidate_id": p.selected_candidate_id,
                "candidates": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "type": c.type,
                        "context": c.context,
                        "match_score": c.match_score,
                        "match_reason": c.match_reason,
                        "is_create_new": c.is_create_new,
                    }
                    for c in p.candidates
                ],
            }
            for p in proposal_set.entity_proposals
        ],
        "relationship_proposals": [
            {
                "proposal_id": p.proposal_id,
                "action": p.action,
                "source_mention": p.source_mention,
                "target_mention": p.target_mention,
                "relationship_type": p.relationship_type,
                "old_type": p.old_type,
                "reason": p.reason,
                "approved": p.approved,
            }
            for p in proposal_set.relationship_proposals
        ],
        "document_proposals": [
            {
                "proposal_id": p.proposal_id,
                "action": p.action,
                "entity_mention": p.entity_mention,
                "title": p.title,
                "content": p.content,
                "approved": p.approved,
            }
            for p in proposal_set.document_proposals
        ],
    }


def execute_approved_proposals(
    proposal_set: ProposalSet,
    user_selections: dict,
) -> dict:
    """
    Execute only the approved proposals.
    
    Args:
        proposal_set: The proposal set to execute
        user_selections: Dict with user's selections:
            - entity_selections: {proposal_id: selected_candidate_id or "new"}
            - entity_descriptions: {proposal_id: "description for new entity"}
            - relationship_approvals: {proposal_id: True/False}
            - document_approvals: {proposal_id: True/False}
    
    Returns:
        Dict with created entity IDs and results
    """
    from soml.core.types import Person, Project, Goal, Event, Period, EntityType, Source
    from soml.storage.registry import RegistryStore
    from soml.storage.markdown import MarkdownStore
    from soml.storage.graph import GraphStore
    from soml.core.config import settings
    from soml.mcp import tools as mcp_tools
    from uuid import uuid4
    
    logger.debug(f"Executing approved proposals: {proposal_set.proposal_set_id}")
    logger.debug(f"Entities: {len(proposal_set.entity_proposals)}, Relationships: {len(proposal_set.relationship_proposals)}, Documents: {len(proposal_set.document_proposals)}")
    
    # Get storage instances
    registry = RegistryStore()
    md_store = MarkdownStore()
    graph_store = GraphStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    
    results = {
        "entities_created": [],
        "entities_linked": [],
        "relationships_created": [],
        "documents_created": [],
        "errors": [],
    }
    
    # Map mention -> entity_id for relationship resolution
    mention_to_id: dict[str, str] = {}
    
    # Process entity selections
    entity_selections = user_selections.get("entity_selections", {})
    entity_descriptions = user_selections.get("entity_descriptions", {})
    
    for proposal in proposal_set.entity_proposals:
        selected_id = entity_selections.get(proposal.proposal_id)
        
        # Fall back to auto-selected candidate if user didn't make explicit selection
        if selected_id is None:
            selected_id = proposal.selected_candidate_id
            logger.info(f"Using auto-selected candidate for {proposal.mention}: {selected_id}")
        
        if selected_id is None:
            # Still no selection, skip
            logger.info(f"Skipping entity {proposal.mention} - no selection")
            continue
        
        if selected_id == "new" or selected_id == "":
            # Create new entity directly without resolution (we already resolved in proposal phase)
            description = entity_descriptions.get(proposal.proposal_id, "")
            context = proposal.inferred_context
            if description:
                context = f"{context}; {description}" if context else description
            
            try:
                if proposal.inferred_type == "person":
                    entity = Person(
                        id=uuid4(),
                        name=proposal.mention,
                        disambiguator=context,
                        source=Source.USER,
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.PERSON,
                        name=entity.name,
                        checksum=md_store._compute_checksum(""),
                        content="",
                        metadata={"disambiguator": context} if context else None,
                    )
                    graph_store.upsert_node(entity)
                    
                elif proposal.inferred_type == "project":
                    entity = Project(
                        id=uuid4(),
                        name=proposal.mention,
                        description=context,
                        source=Source.USER,
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.PROJECT,
                        name=entity.name,
                        checksum=md_store._compute_checksum(""),
                        content="",
                    )
                    graph_store.upsert_node(entity)
                    
                elif proposal.inferred_type == "goal":
                    entity = Goal(
                        id=uuid4(),
                        title=proposal.mention,
                        description=context,
                        source=Source.USER,
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.GOAL,
                        name=entity.title,
                        checksum=md_store._compute_checksum(""),
                        content="",
                    )
                    graph_store.upsert_node(entity)
                    
                elif proposal.inferred_type == "event":
                    entity = Event(
                        id=uuid4(),
                        title=proposal.mention,
                        source=Source.USER,
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.EVENT,
                        name=entity.title,
                        checksum=md_store._compute_checksum(""),
                        content="",
                    )
                    graph_store.upsert_node(entity)
                    
                elif proposal.inferred_type == "period":
                    entity = Period(
                        id=uuid4(),
                        name=proposal.mention,
                        source=Source.USER,
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.PERIOD,
                        name=entity.name,
                        checksum=md_store._compute_checksum(""),
                        content="",
                    )
                    graph_store.upsert_node(entity)
                    
                else:
                    # Unknown type - flag for review instead of defaulting
                    logger.warning(f"Unknown entity type '{proposal.inferred_type}' for {proposal.mention}, creating as person with review flag")
                    entity = Person(
                        id=uuid4(),
                        name=proposal.mention,
                        disambiguator=context,
                        source=Source.USER,
                        needs_review=True,
                        review_reason=f"Auto-created with unknown type '{proposal.inferred_type}' - please verify",
                    )
                    filepath = md_store.write(entity)
                    registry.index(
                        doc_id=str(entity.id),
                        path=filepath,
                        entity_type=EntityType.PERSON,
                        name=entity.name,
                        checksum=md_store._compute_checksum(""),
                        content="",
                        metadata={"disambiguator": context, "needs_review": True} if context else {"needs_review": True},
                    )
                    graph_store.upsert_node(entity)
                
                mention_to_id[proposal.mention.lower()] = str(entity.id)
                results["entities_created"].append({
                    "id": str(entity.id),
                    "name": proposal.mention,
                    "type": proposal.inferred_type,
                })
                logger.info(f"Created {proposal.inferred_type}: {proposal.mention} ({entity.id})")
                
            except Exception as e:
                logger.error(f"Failed to create {proposal.mention}: {e}")
                results["errors"].append(f"Failed to create {proposal.mention}: {str(e)}")
        else:
            # User selected existing entity
            mention_to_id[proposal.mention.lower()] = selected_id
            results["entities_linked"].append({
                "id": selected_id,
                "mention": proposal.mention,
            })
    
    # Process relationship approvals
    relationship_approvals = user_selections.get("relationship_approvals", {})
    
    for proposal in proposal_set.relationship_proposals:
        approved = relationship_approvals.get(proposal.proposal_id)
        
        if not approved:
            continue
        
        # Resolve source and target IDs
        source_id = mention_to_id.get(proposal.source_mention.lower())
        target_id = mention_to_id.get(proposal.target_mention.lower())
        
        if not source_id or not target_id:
            results["errors"].append(
                f"Cannot create relationship: {proposal.source_mention} or {proposal.target_mention} not resolved"
            )
            continue
        
        if proposal.action == "add":
            result = mcp_tools.add_relationship(
                source_id=source_id,
                target_id=target_id,
                rel_type=proposal.relationship_type,
                reason=proposal.reason,
            )
        elif proposal.action == "replace":
            result = mcp_tools.replace_relationship(
                source_id=source_id,
                target_id=target_id,
                old_type=proposal.old_type,
                new_type=proposal.relationship_type,
                reason=proposal.reason,
            )
        else:
            continue
        
        if result.action in ["created", "updated"]:
            results["relationships_created"].append({
                "source_id": source_id,
                "target_id": target_id,
                "type": proposal.relationship_type,
            })
        else:
            results["errors"].append(f"Relationship failed: {result.error}")
    
    # Process document update approvals
    document_approvals = user_selections.get("document_approvals", {})
    
    logger.debug(f"Processing {len(proposal_set.document_proposals)} document proposals")
    
    for proposal in proposal_set.document_proposals:
        # Check approval - default to True if proposal was pre-approved
        approved = document_approvals.get(proposal.proposal_id, proposal.approved)
        
        
        if not approved:
            continue
        
        # Find entity ID for this document update
        entity_id = mention_to_id.get(proposal.entity_mention.lower())
        
        if not entity_id:
            # Try to find by name in registry
            matches = registry.search(proposal.entity_mention, limit=1)
            if matches:
                entity_id = matches[0].get("id")
        
        if not entity_id:
            logger.warning(f"Cannot update document: entity '{proposal.entity_mention}' not found")
            results["errors"].append(f"Cannot update document: entity '{proposal.entity_mention}' not found")
            continue
        
        try:
            # Append to the entity's general info document
            from soml.core.types import Document, DocumentType, Source
            from datetime import datetime
            from uuid import UUID as UUIDType
            
            
            # Get or create general info document
            existing_doc = md_store.get_general_info_document(entity_id)
            
            if existing_doc:
                # Append to existing
                doc_id = existing_doc.get("metadata", {}).get("id")
                
                if doc_id:
                    success = md_store.append_to_document(
                        doc_id=doc_id,
                        content=f"\n\n**Update ({datetime.now().strftime('%Y-%m-%d')}):** {proposal.content}",
                        source=Source.AGENT,
                    )
                    if success:
                        results["documents_created"].append({
                            "action": "appended",
                            "entity_name": proposal.entity_mention,
                            "content": proposal.content,
                        })
                        logger.info(f"Appended content to document {doc_id}")
                    else:
                        results["errors"].append(f"Failed to append to document for {proposal.entity_mention}")
                        logger.error(f"append_to_document returned False for {doc_id}")
            else:
                # Get entity type for the document
                entity_data = registry.get(entity_id)
                entity_type_str = entity_data.get("type", "person") if entity_data else "person"
                entity_type = EntityType(entity_type_str)
                
                # Convert entity_id to UUID
                entity_uuid = UUIDType(entity_id) if isinstance(entity_id, str) else entity_id
                
                # Create new general info document
                doc = Document(
                    id=uuid4(),
                    title=f"General Info - {proposal.entity_mention}",
                    content=proposal.content,
                    document_type=DocumentType.GENERAL_INFO,
                    parent_entity_id=entity_uuid,
                    parent_entity_type=entity_type,
                    source=Source.AGENT,
                    locked=True,
                )
                filepath = md_store.write_document(doc)
                logger.info(f"Created general info document at {filepath}")
                
                # Also index in registry
                registry.index(
                    doc_id=str(doc.id),
                    path=filepath,
                    entity_type=EntityType.DOCUMENT,
                    name=doc.title,
                    checksum=md_store._compute_checksum(doc.content),
                    content=doc.content,
                    document_type="general_info",
                    parent_entity_id=entity_id,
                    parent_entity_type=entity_type_str,
                    locked=True,
                )
                
                results["documents_created"].append({
                    "action": "created",
                    "entity_name": proposal.entity_mention,
                    "content": proposal.content,
                })
                
        except Exception as e:
            logger.error(f"Failed to update document for {proposal.entity_mention}: {e}")
            import traceback
            traceback.print_exc()
            results["errors"].append(f"Document update failed: {str(e)}")
    
    # Update conversation context with all resolved IDs
    if proposal_set.conversation_id and mention_to_id:
        try:
            from soml.storage.conversations import ConversationStore
            conv_store = ConversationStore()
            for mention, entity_id in mention_to_id.items():
                conv_store.update_entity_context(proposal_set.conversation_id, mention, entity_id)
        except Exception as e:
            logger.warning(f"Failed to update conversation context: {e}")
    
    return results

