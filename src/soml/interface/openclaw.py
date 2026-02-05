"""
Openclaw Integration - Skill handlers for scheduling and notifications.

Exposes Story of My Life as an Openclaw skill with:
- Scheduled tasks (open loop detection, memory synthesis, entity resolution)
- Tool functions (recall, add_note, timeline, etc.)
- Notification outputs

Openclaw handles:
- Cron-based scheduling
- Message routing
- Conversation state
- Notification delivery
"""

import json
from datetime import datetime, timedelta
from typing import Any

from soml.core.config import get_logger
from soml.crew.crew import SOMLCrew, get_crew
from soml.mcp import tools as mcp_tools

logger = get_logger("openclaw")


class OpenclaawSkill:
    """
    Openclaw skill handler for Story of My Life.
    
    Provides scheduled tasks and tool functions that
    Openclaw can invoke.
    """
    
    def __init__(self):
        self.crew = get_crew()
    
    # ==========================================
    # Scheduled Tasks
    # ==========================================
    
    async def detect_open_loops(self) -> dict[str, Any]:
        """
        Daily task: Detect open loops and schedule check-ins.
        
        Scheduled via Openclaw cron: "0 9 * * *" (9am daily)
        
        Returns structured data for Openclaw to schedule notifications.
        """
        logger.info("Running scheduled open loop detection")
        
        loops = mcp_tools.detect_open_loops()
        
        # Format for Openclaw scheduling
        scheduled_notifications = []
        for loop in loops:
            if loop.get("urgency", 0) > 30:  # Only notify for notable loops
                scheduled_notifications.append({
                    "type": "check_in",
                    "entity_id": loop.get("entity_id"),
                    "prompt": loop.get("prompt"),
                    "urgency": loop.get("urgency"),
                    "suggested_time": loop.get("suggested_timing"),
                })
        
        return {
            "detected": len(loops),
            "scheduled": len(scheduled_notifications),
            "notifications": scheduled_notifications,
        }
    
    async def synthesize_weekly(self) -> dict[str, Any]:
        """
        Weekly task: Synthesize memories from past week.
        
        Scheduled via Openclaw cron: "0 10 * * 0" (10am Sundays)
        """
        logger.info("Running weekly memory synthesis")
        
        memories = mcp_tools.synthesize_memories()
        
        return {
            "memories_created": len(memories),
            "summary": "Weekly synthesis complete",
        }
    
    async def scan_duplicates(self) -> dict[str, Any]:
        """
        Weekly task: Scan for duplicate entities.
        
        Scheduled via Openclaw cron: "0 11 * * 0" (11am Sundays)
        """
        logger.info("Running entity resolution scan")
        
        duplicates = mcp_tools.find_duplicates()
        
        return {
            "potential_duplicates": len(duplicates),
            "proposals": duplicates,
        }
    
    # ==========================================
    # Tool Functions
    # ==========================================
    
    async def recall(self, query: str) -> dict[str, Any]:
        """Search the knowledge graph."""
        result = self.crew.query(query)
        
        return {
            "answer": result.answer,
            "sources": len(result.sources) if result.sources else 0,
        }
    
    async def add_note(self, content: str) -> dict[str, Any]:
        """Add new content to the knowledge graph."""
        result = self.crew.ingest(content)
        
        return {
            "success": result.success,
            "message": result.message,
        }
    
    async def timeline(self, days: int = 7) -> dict[str, Any]:
        """Get recent timeline."""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        end_date = datetime.now().isoformat()
        
        result = mcp_tools.get_timeline(
            start_date=start_date,
            end_date=end_date,
        )
        
        return {
            "timeline": result,
            "count": len(result),
        }
    
    async def summarize(self, period: str = "week") -> dict[str, Any]:
        """Summarize a time period."""
        result = self.crew.query(f"Summarize what happened in the past {period}")
        
        return {
            "summary": result.answer,
            "success": result.success,
        }
    
    async def get_open_loops(self) -> dict[str, Any]:
        """Get current open loops."""
        loops = mcp_tools.detect_open_loops()
        
        return {
            "loops": loops,
            "count": len(loops),
        }


# Global skill instance
_skill: OpenclaawSkill | None = None


def get_skill() -> OpenclaawSkill:
    """Get or create the global skill instance."""
    global _skill
    if _skill is None:
        _skill = OpenclaawSkill()
    return _skill


async def skill_handler(function_name: str, **kwargs) -> dict[str, Any]:
    """
    Main entry point for Openclaw skill invocation.
    
    This function is registered with Openclaw and called
    when the skill is invoked.
    """
    skill = get_skill()
    
    # Map function names to methods
    handlers = {
        "detect_open_loops": skill.detect_open_loops,
        "synthesize_weekly": skill.synthesize_weekly,
        "scan_duplicates": skill.scan_duplicates,
        "recall": skill.recall,
        "add_note": skill.add_note,
        "timeline": skill.timeline,
        "summarize": skill.summarize,
        "open_loops": skill.get_open_loops,
    }
    
    handler = handlers.get(function_name)
    if not handler:
        return {"error": f"Unknown function: {function_name}"}
    
    try:
        return await handler(**kwargs)
    except Exception as e:
        logger.error(f"Skill handler error: {e}")
        return {"error": str(e)}

