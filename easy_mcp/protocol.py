"""
Model Context Protocol (MCP) and JSON-RPC 2.0 specifications.
Standard specification: https://spec.modelcontextprotocol.io/
Zero external dependencies.
"""

from typing import Any, Dict, Optional

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# Standard JSON-RPC Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP-specific error codes
RESOURCE_NOT_FOUND = -32002

# Standard MCP Methods
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"
METHOD_PING = "ping"
METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"
METHOD_RESOURCES_LIST = "resources/list"
METHOD_RESOURCES_READ = "resources/read"
METHOD_PROMPTS_LIST = "prompts/list"
METHOD_PROMPTS_GET = "prompts/get"


class MCPError(Exception):
    """Base exception for MCP and JSON-RPC errors."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class ParseError(MCPError):
    def __init__(self, message: str = "Parse error", data: Any = None):
        super().__init__(PARSE_ERROR, message, data)


class InvalidRequestError(MCPError):
    def __init__(self, message: str = "Invalid Request", data: Any = None):
        super().__init__(INVALID_REQUEST, message, data)


class MethodNotFoundError(MCPError):
    def __init__(self, message: str = "Method not found", data: Any = None):
        super().__init__(METHOD_NOT_FOUND, message, data)


class InvalidParamsError(MCPError):
    def __init__(self, message: str = "Invalid params", data: Any = None):
        super().__init__(INVALID_PARAMS, message, data)


class InternalError(MCPError):
    def __init__(self, message: str = "Internal error", data: Any = None):
        super().__init__(INTERNAL_ERROR, message, data)


def make_jsonrpc_response(request_id: Any, result: Any) -> Dict[str, Any]:
    """Build a compliant JSON-RPC 2.0 response."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result
    }


def make_jsonrpc_error(
    request_id: Any,
    code: int,
    message: str,
    data: Optional[Any] = None
) -> Dict[str, Any]:
    """Build a compliant JSON-RPC 2.0 error response."""
    err: Dict[str, Any] = {
        "code": code,
        "message": message
    }
    if data is not None:
        err["data"] = data
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": err
    }
