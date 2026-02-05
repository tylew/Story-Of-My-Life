"""
Entity Resolution - Deterministic entity matching and disambiguation.

This module implements codified entity resolution logic:
1. Exact name match
2. Alias match
3. Fuzzy match with threshold
4. Conversation context match

The resolution is deterministic - same inputs always produce same outputs.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from soml.core.config import get_logger
from soml.core.types import EntityType
from soml.storage.registry import RegistryStore
from soml.storage.markdown import MarkdownStore

logger = get_logger("mcp.resolution")


@dataclass
class ResolutionResult:
    """Result of entity resolution."""
    
    found: bool
    """Whether an existing entity was found."""
    
    entity_id: str | None
    """ID of the matched entity (if found)."""
    
    entity_name: str | None
    """Name of the matched entity (if found)."""
    
    match_type: str | None
    """How the match was made: 'exact', 'alias', 'fuzzy', 'context'."""
    
    match_score: float
    """How well the name matched (0.0-1.0). 1.0 = exact match."""
    
    candidates: list[dict] | None = None
    """List of candidate matches if ambiguous."""
    
    needs_confirmation: bool = False
    """Whether user confirmation is needed."""


class EntityResolver:
    """
    Deterministic entity resolution engine.
    
    Resolution flow:
    1. Normalize name (lowercase, strip whitespace)
    2. Check exact match in registry
    3. Check alias matches
    4. Check fuzzy matches (Levenshtein > 0.85)
    5. Check conversation context for references
    
    If multiple matches with similar scores, returns candidates for confirmation.
    """
    
    # Similarity thresholds
    EXACT_THRESHOLD = 1.0
    ALIAS_THRESHOLD = 0.95
    FUZZY_THRESHOLD = 0.85
    AMBIGUOUS_THRESHOLD = 0.05  # Difference to consider matches ambiguous
    
    def __init__(self):
        self.registry = RegistryStore()
        self.md_store = MarkdownStore()
        # Alias cache: name -> entity_id
        self._alias_cache: dict[str, str] = {}
    
    def resolve(
        self,
        name: str,
        entity_type: EntityType | str,
        context: str | None = None,
        conversation_entities: dict[str, str] | None = None,
    ) -> ResolutionResult:
        """
        Resolve a name to an existing entity or indicate it's new.
        
        Args:
            name: The name to resolve
            entity_type: Type of entity to search for
            context: Additional context for disambiguation
            conversation_entities: Dict of name -> entity_id from conversation
        
        Returns:
            ResolutionResult with match info or candidates
        """
        normalized = self._normalize(name)
        type_str = entity_type.value if isinstance(entity_type, EntityType) else entity_type
        
        # Step 1: Check exact match
        exact = self._find_exact(normalized, type_str)
        if exact:
            return ResolutionResult(
                found=True,
                entity_id=exact["id"],
                entity_name=exact["name"],
                match_type="exact",
                match_score=1.0,
            )
        
        # Step 2: Check conversation context
        if conversation_entities:
            for ctx_name, ctx_id in conversation_entities.items():
                if self._normalize(ctx_name) == normalized:
                    return ResolutionResult(
                        found=True,
                        entity_id=ctx_id,
                        entity_name=ctx_name,
                        match_type="context",
                        match_score=0.95,
                    )
                # Check if name is a pronoun or reference resolved in context
                if normalized in ["he", "she", "they", "the project", "dad", "mom"]:
                    # This would need conversation history to resolve properly
                    pass
        
        # Step 3: Check alias matches
        alias_match = self._find_alias(normalized, type_str)
        if alias_match:
            return ResolutionResult(
                found=True,
                entity_id=alias_match["id"],
                entity_name=alias_match["name"],
                match_type="alias",
                match_score=0.95,
            )
        
        # Step 4: Fuzzy matching
        fuzzy_matches = self._find_fuzzy(normalized, type_str, context)
        
        if not fuzzy_matches:
            # No matches found - definitely new
            return ResolutionResult(
                found=False,
                entity_id=None,
                entity_name=None,
                match_type=None,
                match_score=0.0,
            )
        
        # Check if single clear winner
        if len(fuzzy_matches) == 1 and fuzzy_matches[0]["score"] >= self.FUZZY_THRESHOLD:
            return ResolutionResult(
                found=True,
                entity_id=fuzzy_matches[0]["id"],
                entity_name=fuzzy_matches[0]["name"],
                match_type="fuzzy",
                match_score=fuzzy_matches[0]["score"],
            )
        
        # Check if top match is significantly better
        if len(fuzzy_matches) >= 2:
            top = fuzzy_matches[0]["score"]
            second = fuzzy_matches[1]["score"]
            
            if top >= self.FUZZY_THRESHOLD and (top - second) > self.AMBIGUOUS_THRESHOLD:
                return ResolutionResult(
                    found=True,
                    entity_id=fuzzy_matches[0]["id"],
                    entity_name=fuzzy_matches[0]["name"],
                    match_type="fuzzy",
                    match_score=fuzzy_matches[0]["score"],
                )
        
        # Ambiguous - return candidates for confirmation
        if fuzzy_matches[0]["score"] >= 0.5:  # At least somewhat similar
            return ResolutionResult(
                found=False,
                entity_id=None,
                entity_name=None,
                match_type=None,
                match_score=0.0,
                candidates=fuzzy_matches[:5],
                needs_confirmation=True,
            )
        
        # No good matches
        return ResolutionResult(
            found=False,
            entity_id=None,
            entity_name=None,
            match_type=None,
            match_score=0.0,
        )
    
    def add_alias(self, entity_id: str, alias: str) -> None:
        """Add an alias for an entity."""
        normalized = self._normalize(alias)
        self._alias_cache[normalized] = entity_id
        # TODO: Persist to storage
    
    def _normalize(self, name: str) -> str:
        """Normalize a name for matching."""
        return name.lower().strip()
    
    def _find_exact(self, normalized: str, entity_type: str) -> dict | None:
        """Find exact name match."""
        entities = self.registry.list_by_type(entity_type)
        
        for entity in entities:
            entity_name = entity.get("name", "")
            if self._normalize(entity_name) == normalized:
                return entity
        
        return None
    
    def _find_alias(self, normalized: str, entity_type: str) -> dict | None:
        """Find alias match."""
        entity_id = self._alias_cache.get(normalized)
        if entity_id:
            return self.registry.get(entity_id)
        return None
    
    def _find_fuzzy(
        self,
        normalized: str,
        entity_type: str,
        context: str | None = None,
    ) -> list[dict]:
        """Find fuzzy matches using Levenshtein similarity."""
        entities = self.registry.list_by_type(entity_type)
        matches = []
        
        for entity in entities:
            entity_name = entity.get("name", "")
            if not entity_name:
                continue
            
            score = self._levenshtein_similarity(normalized, self._normalize(entity_name))
            
            # Boost score if context matches
            if context and entity.get("disambiguator"):
                context_norm = self._normalize(context)
                disamb_norm = self._normalize(entity.get("disambiguator", ""))
                if context_norm in disamb_norm or disamb_norm in context_norm:
                    score = min(1.0, score + 0.1)
            
            # Also check for partial name matches (e.g., "Craig" matching "Craig Lewis")
            name_parts = set(normalized.split())
            entity_parts = set(self._normalize(entity_name).split())
            
            if name_parts & entity_parts:  # At least one word in common
                shared = len(name_parts & entity_parts)
                total = max(len(name_parts), len(entity_parts))
                partial_score = shared / total
                score = max(score, partial_score)
            
            if score > 0.3:  # Minimum threshold to consider
                matches.append({
                    "id": entity.get("id"),
                    "name": entity_name,
                    "type": entity.get("type"),
                    "disambiguator": entity.get("disambiguator"),
                    "score": score,
                })
        
        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio (0.0-1.0)."""
        if s1 == s2:
            return 1.0
        
        if not s1 or not s2:
            return 0.0
        
        # Simple Levenshtein distance
        m, n = len(s1), len(s2)
        
        if m > n:
            s1, s2 = s2, s1
            m, n = n, m
        
        d = list(range(m + 1))
        
        for i in range(1, n + 1):
            prev, d[0] = d[0], i
            for j in range(1, m + 1):
                temp = d[j]
                if s1[j - 1] == s2[i - 1]:
                    d[j] = prev
                else:
                    d[j] = min(d[j], d[j - 1], prev) + 1
                prev = temp
        
        max_len = max(m, n)
        return 1.0 - (d[m] / max_len)

