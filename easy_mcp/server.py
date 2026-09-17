"""
Core EasyMCP Server implementation.
Handles stdio JSON-RPC 2.0 communication with Claude Desktop / Claude Code.
Zero external dependencies.
"""

import json
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

from easy_mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    MCP_PROTOCOL_VERSION,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_NOT_FOUND,
    METHOD_PING,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    PARSE_ERROR,
    make_jsonrpc_error,
    make_jsonrpc_response,
)
from easy_mcp.schema import function_to_tool_schema


class EasyMCP:
    """
    Lightweight, zero-dependency Model Context Protocol (MCP) Server.
    
    Example:
        mcp = EasyMCP("math-tools", version="1.0.0")

        @mcp.tool()
        def add(a: float, b: float) -> float:
            '''Add two numbers together.'''
            return a + b

        if __name__ == "__main__":
            mcp.run()
    """

    def __init__(self, name: str = "easy-mcp-server", version: str = "0.1.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, Dict[str, Any]] = {}

    def tool(self, name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a Python function as an MCP tool."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            schema = function_to_tool_schema(func, name=tool_name, description=description)
            self._tools[tool_name] = func
            self._tool_schemas[tool_name] = schema
            return func
        return decorator

    def register_tool(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        """Programmatic way to register a tool without decorator."""
        tool_name = name or func.__name__
        schema = function_to_tool_schema(func, name=tool_name, description=description)
        self._tools[tool_name] = func
        self._tool_schemas[tool_name] = schema

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return list of registered MCP tools."""
        return list(self._tool_schemas.values())

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a tool locally and return MCP content block result."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found.")
            
        args = arguments or {}
        func = self._tools[name]
        
        try:
            res = func(**args)
            
            # Format as MCP content block
            if isinstance(res, (dict, list)):
                text_content = json.dumps(res, ensure_ascii=False, indent=2)
            else:
                text_content = str(res)
                
            return {
                "content": [
                    {
                        "type": "text",
                        "text": text_content
                    }
                ],
                "isError": False
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool '{name}': {str(e)}\n{traceback.format_exc()}"
                    }
                ],
                "isError": True
            }

    def handle_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a single JSON-RPC 2.0 request."""
        req_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params", {})

        # Handle notifications (requests without id)
        is_notification = (req_id is None)

        if method == METHOD_INITIALIZE:
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version
                }
            }
            return make_jsonrpc_response(req_id, result)

        elif method == METHOD_INITIALIZED:
            # Notification from client that initialization is complete
            return None

        elif method == METHOD_PING:
            return make_jsonrpc_response(req_id, {})

        elif method == METHOD_TOOLS_LIST:
            result = {
                "tools": self.list_tools()
            }
            return make_jsonrpc_response(req_id, result)

        elif method == METHOD_TOOLS_CALL:
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not tool_name:
                return make_jsonrpc_error(req_id, INVALID_PARAMS, "Missing required parameter: 'name'")
                
            if tool_name not in self._tools:
                return make_jsonrpc_error(req_id, METHOD_NOT_FOUND, f"Tool '{tool_name}' not found.")

            res = self.call_tool(tool_name, arguments)
            return make_jsonrpc_response(req_id, res)

        else:
            if is_notification:
                return None
            return make_jsonrpc_error(req_id, METHOD_NOT_FOUND, f"Unknown method: '{method}'")

    def run_stdio(self):
        """Run the stdio JSON-RPC loop connecting with Claude Desktop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request_data = json.loads(line)
            except json.JSONDecodeError as e:
                err_resp = make_jsonrpc_error(None, PARSE_ERROR, f"JSON parse error: {str(e)}")
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            response = self.handle_request(request_data)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()

    def run(self):
        """Alias for run_stdio."""
        self.run_stdio()

    def get_claude_config(self, script_path: Optional[str] = None) -> Dict[str, Any]:
        """Generate the JSON snippet for claude_desktop_config.json."""
        target_script = script_path or os.path.abspath(sys.argv[0])
        return {
            "mcpServers": {
                self.name: {
                    "command": "python",
                    "args": [target_script]
                }
            }
        }

    def print_claude_config(self, script_path: Optional[str] = None):
        """Print formatted JSON for Claude Desktop configuration."""
        cfg = self.get_claude_config(script_path)
        print(json.dumps(cfg, indent=2))
