"""
MCP Server - Model Context Protocol server for Claude/Cursor integration.

Exposes Story of My Life as an MCP tool server with smart, deterministic tools:
- Entity operations (upsert_person, upsert_project, etc.)
- Relationship operations (link_entities, unlink_entities)
- Query operations (search, timeline, semantic_search)
- Intelligence operations (open_loops, find_duplicates)
- Batch processing (process_extraction)

Tools are designed to be high-level - agent describes WHAT, tool handles HOW.
"""

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.server import serve

from soml.core.config import settings, setup_logging, get_logger
from soml.mcp import tools as mcp_tools

logger = get_logger("mcp_server")


class MCPServer:
    """
    MCP (Model Context Protocol) server for SOML.
    
    Provides a WebSocket interface that Claude and other
    MCP-compatible clients can use to interact with the
    knowledge graph.
    """
    
    def __init__(self):
        self.tools = self._define_tools()
    
    def _define_tools(self) -> list[dict]:
        """Define available MCP tools."""
        return [
            # ===================
            # Entity Upsert Tools
            # ===================
            {
                "name": "upsert_person",
                "description": "Create or update a person in the knowledge graph. Handles entity resolution automatically.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Person's name"
                        },
                        "context": {
                            "type": "string",
                            "description": "Disambiguating context (e.g., 'user's father', 'coworker from Google')"
                        },
                        "data": {
                            "type": "object",
                            "description": "Additional data (email, phone, notes)",
                            "properties": {
                                "email": {"type": "string"},
                                "phone": {"type": "string"},
                                "notes": {"type": "string"}
                            }
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "upsert_project",
                "description": "Create or update a project/company in the knowledge graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Project/company name"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context"
                        },
                        "data": {
                            "type": "object",
                            "description": "Additional data (description, status)",
                            "properties": {
                                "description": {"type": "string"},
                                "status": {"type": "string", "enum": ["active", "completed", "on_hold", "cancelled"]}
                            }
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "upsert_goal",
                "description": "Create or update a personal goal.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Goal title"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context"
                        },
                        "data": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "target_date": {"type": "string"},
                                "progress": {"type": "integer", "minimum": 0, "maximum": 100}
                            }
                        }
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "upsert_event",
                "description": "Create or update an event (specific occurrence on a date).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Event title"
                        },
                        "on_date": {
                            "type": "string",
                            "description": "Date of the event (ISO format or natural language)"
                        },
                        "context": {
                            "type": "string",
                            "description": "Event description/context"
                        },
                        "data": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"},
                                "temporal_state": {"type": "string", "enum": ["observed", "planned", "cancelled"]}
                            }
                        }
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "upsert_period",
                "description": "Create or update a period (span of time like 'job at Company X', 'college years').",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Descriptive name for the period (NOT user's literal phrase)"
                        },
                        "context": {
                            "type": "string",
                            "description": "Description of what this period represents"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date (ISO format)"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date (ISO format)"
                        }
                    },
                    "required": ["name"]
                }
            },
            
            # ===================
            # Relationship Tools
            # ===================
            {
                "name": "link_entities",
                "description": "Create a relationship between two entities. Idempotent - won't create duplicates.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source entity ID"
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Target entity ID"
                        },
                        "rel_type": {
                            "type": "string",
                            "description": "Relationship type (family, friend, works_at, invested_in, etc.)"
                        },
                        "properties": {
                            "type": "object",
                            "description": "Additional properties (confidence, notes)"
                        }
                    },
                    "required": ["source_id", "target_id", "rel_type"]
                }
            },
            {
                "name": "unlink_entities",
                "description": "Remove a relationship between two entities.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "target_id": {"type": "string"},
                        "rel_type": {"type": "string"}
                    },
                    "required": ["source_id", "target_id", "rel_type"]
                }
            },
            {
                "name": "get_entity_relationships",
                "description": "Get all relationships for an entity. Use this BEFORE proposing relationship changes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {
                            "type": "string",
                            "description": "Entity ID to get relationships for"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["outgoing", "incoming", "both"],
                            "description": "Direction of relationships to fetch"
                        },
                        "include_entity_details": {
                            "type": "boolean",
                            "description": "Include name/type of related entities"
                        }
                    },
                    "required": ["entity_id"]
                }
            },
            {
                "name": "add_relationship",
                "description": "Add a new relationship between entities. Use for creating new relationships.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source entity ID"
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Target entity ID"
                        },
                        "rel_type": {
                            "type": "string",
                            "description": "Relationship type"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this relationship is being created"
                        }
                    },
                    "required": ["source_id", "target_id", "rel_type"]
                }
            },
            {
                "name": "replace_relationship",
                "description": "Replace an existing relationship type. Use for transitions like works_with → worked_with.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_id": {
                            "type": "string",
                            "description": "Source entity ID"
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Target entity ID"
                        },
                        "old_type": {
                            "type": "string",
                            "description": "Current relationship type to replace"
                        },
                        "new_type": {
                            "type": "string",
                            "description": "New relationship type"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this change is happening"
                        }
                    },
                    "required": ["source_id", "target_id", "old_type", "new_type"]
                }
            },
            {
                "name": "apply_relationship_proposal",
                "description": "Apply a user-approved relationship proposal. Call ONLY after user approval.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["add", "replace", "remove"],
                            "description": "Type of change"
                        },
                        "source_id": {"type": "string"},
                        "target_id": {"type": "string"},
                        "new_type": {
                            "type": "string",
                            "description": "New relationship type (for add/replace)"
                        },
                        "old_type": {
                            "type": "string",
                            "description": "Existing relationship type (for replace/remove)"
                        },
                        "reason": {"type": "string"}
                    },
                    "required": ["action", "source_id", "target_id"]
                }
            },
            
            # ===================
            # Batch Processing
            # ===================
            {
                "name": "process_extraction",
                "description": "Process a batch of extracted entities and relationships. Main ingestion tool.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "description": "List of entities [{name, type, context}, ...]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "context": {"type": "string"}
                                },
                                "required": ["name", "type"]
                            }
                        },
                        "relationships": {
                            "type": "array",
                            "description": "List of relationships [{source_name, target_name, type}, ...]",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_name": {"type": "string"},
                                    "target_name": {"type": "string"},
                                    "type": {"type": "string"}
                                },
                                "required": ["source_name", "target_name", "type"]
                            }
                        },
                        "conversation_id": {
                            "type": "string",
                            "description": "Optional conversation ID for context"
                        }
                    },
                    "required": ["entities", "relationships"]
                }
            },
            
            # ===================
            # Query Tools
            # ===================
            {
                "name": "get_entity",
                "description": "Get an entity by ID with full content.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"}
                    },
                    "required": ["entity_id"]
                }
            },
            {
                "name": "search_entities",
                "description": "Search for entities by name or content.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Optional type filter (person, project, goal, event, period)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_relationships",
                "description": "Get relationships for an entity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "direction": {
                            "type": "string",
                            "enum": ["outgoing", "incoming", "both"],
                            "default": "both"
                        },
                        "rel_type": {
                            "type": "string",
                            "description": "Optional relationship type filter"
                        }
                    },
                    "required": ["entity_id"]
                }
            },
            {
                "name": "get_timeline",
                "description": "Get timeline of events.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Entity types to include"
                        }
                    }
                }
            },
            
            # ===================
            # Intelligence Tools
            # ===================
            {
                "name": "detect_open_loops",
                "description": "Detect open loops (stale relationships, stalled projects, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "find_duplicates",
                "description": "Find potential duplicate entities in the knowledge graph.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            
            # ===================
            # Document Tools
            # ===================
            {
                "name": "append_to_document",
                "description": "Append content to an entity's General Info document.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "content": {"type": "string"},
                        "source": {
                            "type": "string",
                            "enum": ["user", "agent"],
                            "default": "agent"
                        }
                    },
                    "required": ["entity_id", "content"]
                }
            },
            {
                "name": "get_general_info",
                "description": "Get the General Info document for an entity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"}
                    },
                    "required": ["entity_id"]
                }
            }
        ]
    
    async def handle_message(self, message: dict) -> dict:
        """Handle an incoming MCP message."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")
        
        if method == "initialize":
            return {
                "id": msg_id,
                "result": {
                    "protocolVersion": "0.1.0",
                    "serverInfo": {
                        "name": "story-of-my-life",
                        "version": "0.2.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "id": msg_id,
                "result": {
                    "tools": self.tools
                }
            }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            result = await self._execute_tool(tool_name, tool_args)
            
            return {
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, default=str)
                        }
                    ]
                }
            }
        
        else:
            return {
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
    
    async def _execute_tool(self, name: str, args: dict) -> Any:
        """Execute an MCP tool."""
        try:
            # Entity upsert tools
            if name == "upsert_person":
                result = mcp_tools.upsert_person(
                    name=args["name"],
                    context=args.get("context"),
                    data=args.get("data", {}),
                )
                return {"action": result.action, "entity_id": result.entity_id, "entity": result.entity}
            
            elif name == "upsert_project":
                result = mcp_tools.upsert_project(
                    name=args["name"],
                    context=args.get("context"),
                    data=args.get("data", {}),
                )
                return {"action": result.action, "entity_id": result.entity_id, "entity": result.entity}
            
            elif name == "upsert_goal":
                result = mcp_tools.upsert_goal(
                    title=args["title"],
                    context=args.get("context"),
                    data=args.get("data", {}),
                )
                return {"action": result.action, "entity_id": result.entity_id, "entity": result.entity}
            
            elif name == "upsert_event":
                result = mcp_tools.upsert_event(
                    title=args["title"],
                    on_date=args.get("on_date"),
                    context=args.get("context"),
                    data=args.get("data", {}),
                )
                return {"action": result.action, "entity_id": result.entity_id, "entity": result.entity}
            
            elif name == "upsert_period":
                result = mcp_tools.upsert_period(
                    name=args["name"],
                    context=args.get("context"),
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                )
                return {"action": result.action, "entity_id": result.entity_id, "entity": result.entity}
            
            # Relationship tools
            elif name == "link_entities":
                result = mcp_tools.link_entities(
                    source_id=args["source_id"],
                    target_id=args["target_id"],
                    rel_type=args["rel_type"],
                    properties=args.get("properties"),
                )
                return {"action": result.action, "relationship_id": result.relationship_id}
            
            elif name == "unlink_entities":
                success = mcp_tools.unlink_entities(
                    source_id=args["source_id"],
                    target_id=args["target_id"],
                    rel_type=args["rel_type"],
                )
                return {"success": success}
            
            elif name == "get_entity_relationships":
                results = mcp_tools.get_entity_relationships(
                    entity_id=args["entity_id"],
                    direction=args.get("direction", "both"),
                    include_entity_details=args.get("include_entity_details", True),
                )
                return {"relationships": results}
            
            elif name == "add_relationship":
                result = mcp_tools.add_relationship(
                    source_id=args["source_id"],
                    target_id=args["target_id"],
                    rel_type=args["rel_type"],
                    reason=args.get("reason"),
                )
                return {"action": result.action, "relationship_id": result.relationship_id, "error": result.error}
            
            elif name == "replace_relationship":
                result = mcp_tools.replace_relationship(
                    source_id=args["source_id"],
                    target_id=args["target_id"],
                    old_type=args["old_type"],
                    new_type=args["new_type"],
                    reason=args.get("reason"),
                )
                return {"action": result.action, "error": result.error}
            
            elif name == "apply_relationship_proposal":
                result = mcp_tools.apply_relationship_proposal({
                    "action": args["action"],
                    "source_id": args["source_id"],
                    "target_id": args["target_id"],
                    "new_type": args.get("new_type"),
                    "old_type": args.get("old_type"),
                    "reason": args.get("reason"),
                })
                return {"action": result.action, "error": result.error}
            
            # Batch processing
            elif name == "process_extraction":
                result = mcp_tools.process_extraction(
                    entities=args.get("entities", []),
                    relationships=args.get("relationships", []),
                    conversation_id=args.get("conversation_id"),
                )
                return {
                    "entities": [{"action": e.action, "id": e.entity_id} for e in result.entities],
                    "relationships": [{"action": r.action} for r in result.relationships],
                    "needs_confirmation": result.needs_confirmation,
                }
            
            # Query tools
            elif name == "get_entity":
                entity = mcp_tools.get_entity(args["entity_id"])
                return entity or {"error": "Entity not found"}
            
            elif name == "search_entities":
                results = mcp_tools.search_entities(
                    query=args["query"],
                    entity_type=args.get("entity_type"),
                    limit=args.get("limit", 10),
                )
                return {"results": results, "count": len(results)}
            
            elif name == "get_relationships":
                relationships = mcp_tools.get_relationships(
                    entity_id=args["entity_id"],
                    direction=args.get("direction", "both"),
                    rel_type=args.get("rel_type"),
                )
                return {"relationships": relationships}
            
            elif name == "get_timeline":
                timeline = mcp_tools.get_timeline(
                    start_date=args.get("start_date"),
                    end_date=args.get("end_date"),
                    types=args.get("types"),
                )
                return {"timeline": timeline}
            
            # Intelligence tools
            elif name == "detect_open_loops":
                loops = mcp_tools.detect_open_loops()
                return {"loops": loops, "count": len(loops)}
            
            elif name == "find_duplicates":
                duplicates = mcp_tools.find_duplicates()
                return {"duplicates": duplicates}
            
            # Document tools
            elif name == "append_to_document":
                success = mcp_tools.append_to_document(
                    entity_id=args["entity_id"],
                    content=args["content"],
                    source=args.get("source", "agent"),
                )
                return {"success": success}
            
            elif name == "get_general_info":
                doc = mcp_tools.get_general_info(args["entity_id"])
                return doc or {"exists": False}
            
            else:
                return {"error": f"Unknown tool: {name}"}
        
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}
    
    async def handle_connection(self, websocket):
        """Handle a WebSocket connection."""
        logger.info(f"New connection from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    response = await self.handle_message(data)
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "error": {"code": -32700, "message": "Parse error"}
                    }))
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
    
    async def start(self, host: str = None, port: int = None):
        """Start the MCP server."""
        host = host or settings.mcp_host
        port = port or settings.mcp_port
        
        logger.info(f"Starting MCP server on {host}:{port}")
        
        async with serve(self.handle_connection, host, port):
            await asyncio.Future()  # Run forever


def main():
    """Main entry point for MCP server."""
    setup_logging()
    
    server = MCPServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()

