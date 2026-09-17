"""
Model Context Protocol (MCP) and JSON-RPC 2.0 specifications.
Standard specification: https://spec.modelcontextprotocol.io/
"""

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# Standard JSON-RPC Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Standard MCP Methods
METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"
METHOD_PING = "ping"
METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"


def make_jsonrpc_response(request_id, result):
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "result": result
    }


def make_jsonrpc_error(request_id, code, message, data=None):
    err = {
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
