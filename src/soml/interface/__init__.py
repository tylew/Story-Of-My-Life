"""
Interface module - All external interfaces to the SOML system.

This module contains:
- api.py: FastAPI REST API
- cli.py: Command-line interface
- openclaw.py: Openclaw skill integration
- mcp_server.py: MCP (Model Context Protocol) server
"""

from soml.interface.api import app as api_app

__all__ = [
    "api_app",
]

