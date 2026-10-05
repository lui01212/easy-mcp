"""
easy-mcp: Ultra-lightweight, zero-dependency Python framework for Model Context Protocol (MCP).
Build MCP servers for Claude in seconds.
"""

from easy_mcp.server import EasyMCP
from easy_mcp.schema import function_to_tool_schema, function_to_prompt_arguments
from easy_mcp.installer import install_server, get_claude_config_path
from easy_mcp.dev import load_server_from_file, format_server_summary
from easy_mcp.protocol import (
    MCPError,
    ParseError,
    InvalidRequestError,
    MethodNotFoundError,
    InvalidParamsError,
    InternalError,
)

__version__ = "0.3.1"
__all__ = [
    "EasyMCP",
    "function_to_tool_schema",
    "function_to_prompt_arguments",
    "install_server",
    "get_claude_config_path",
    "load_server_from_file",
    "format_server_summary",
    "MCPError",
    "ParseError",
    "InvalidRequestError",
    "MethodNotFoundError",
    "InvalidParamsError",
    "InternalError",
]
