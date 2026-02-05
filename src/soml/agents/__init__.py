"""
SOML Agents Package - DEPRECATED

This package is deprecated. All functionality has been moved to:
- soml/core/llm.py: LLM utilities
- soml/crew/: CrewAI agents
- soml/mcp/: MCP tools
- soml/interface/: API, CLI, MCP server, Openclaw

This __init__.py provides backward compatibility imports.
"""

# Re-export LLM utilities from core for backward compatibility
from soml.core.llm import call_llm, generate_embedding, generate_embeddings_batch, count_tokens

__all__ = [
    "call_llm",
    "generate_embedding",
    "generate_embeddings_batch",
    "count_tokens",
]
