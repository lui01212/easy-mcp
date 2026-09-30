"""
easy-mcp: Ultra-lightweight, zero-dependency Python framework for Model Context Protocol (MCP).
Build MCP servers for Claude in seconds.
"""

from easy_mcp.server import EasyMCP
from easy_mcp.schema import function_to_tool_schema, function_to_prompt_arguments
from easy_mcp.protocol import (
    MCPError,
    ParseError,
    InvalidRequestError,
    MethodNotFoundError,
    InvalidParamsError,
    InternalError,
)

__version__ = "0.2.0"
__all__ = [
    "EasyMCP",
    "function_to_tool_schema",
    "function_to_prompt_arguments",
    "MCPError",
    "ParseError",
    "InvalidRequestError",
    "MethodNotFoundError",
    "InvalidParamsError",
    "InternalError",
]
