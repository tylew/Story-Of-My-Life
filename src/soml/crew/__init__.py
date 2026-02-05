"""
CrewAI Integration Package - Agent orchestration for SOML.

This package provides CrewAI-based agents that use MCP tools
for all storage and retrieval operations.

Components:
- agents.py: Agent definitions (Ingestion, Query, Intelligence)
- tasks.py: Task definitions for agent workflows
- crew.py: Main Crew orchestrator
"""

from soml.crew.crew import SOMLCrew
from soml.crew.agents import (
    create_ingestion_agent,
    create_query_agent,
    create_intelligence_agent,
)
from soml.crew.tasks import (
    create_extraction_task,
    create_query_task,
    create_analysis_task,
)

__all__ = [
    "SOMLCrew",
    "create_ingestion_agent",
    "create_query_agent",
    "create_intelligence_agent",
    "create_extraction_task",
    "create_query_task",
    "create_analysis_task",
]

