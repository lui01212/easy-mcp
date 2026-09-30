"""
Core EasyMCP Server implementation.
Handles stdio JSON-RPC 2.0 communication with Claude Desktop / Claude Code.
Implements Model Context Protocol (MCP) 2024-11-05 Specification for Tools, Resources, and Prompts.
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
    METHOD_PROMPTS_GET,
    METHOD_PROMPTS_LIST,
    METHOD_RESOURCES_LIST,
    METHOD_RESOURCES_READ,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    PARSE_ERROR,
    make_jsonrpc_error,
    make_jsonrpc_response,
)
from easy_mcp.schema import function_to_prompt_arguments, function_to_tool_schema


class EasyMCP:
    """
    Lightweight, zero-dependency Model Context Protocol (MCP) Server.
    
    Example:
        mcp = EasyMCP("my-server", version="0.2.0")

        @mcp.tool()
        def add(a: float, b: float) -> float:
            '''Add two numbers together.'''
            return a + b

        @mcp.resource("memo://notes")
        def get_notes() -> str:
            '''System documentation notes.'''
            return "Server documentation and quick guides."

        @mcp.prompt()
        def code_review(code: str) -> str:
            '''Review code for safety and style.'''
            return f"Please review this code for security issues:\n\n{code}"

        if __name__ == "__main__":
            mcp.run()
    """

    def __init__(
        self,
        name: str = "easy-mcp-server",
        version: str = "0.2.0",
        description: str = ""
    ):
        self.name = name
        self.version = version
        self.description = description
        
        self._tools: Dict[str, Callable] = {}
        self._tool_schemas: Dict[str, Dict[str, Any]] = {}
        
        self._resources: Dict[str, Callable] = {}
        self._resource_meta: Dict[str, Dict[str, Any]] = {}
        
        self._prompts: Dict[str, Callable] = {}
        self._prompt_meta: Dict[str, Dict[str, Any]] = {}

    # ==========================================
    # Tools API
    # ==========================================

    def tool(self, name: Optional[str] = None, description: Optional[str] = None):
        """Decorator to register a Python function as an MCP tool."""
        def decorator(func: Callable):
            self.register_tool(func, name=name, description=description)
            return func
        return decorator

    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Programmatic registration of an MCP tool."""
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

    # ==========================================
    # Resources API
    # ==========================================

    def resource(
        self,
        uri: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: str = "text/plain"
    ):
        """Decorator to register a function as an MCP resource provider."""
        def decorator(func: Callable):
            self.register_resource(
                uri=uri,
                func=func,
                name=name,
                description=description,
                mime_type=mime_type
            )
            return func
        return decorator

    def register_resource(
        self,
        uri: str,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: str = "text/plain"
    ):
        """Programmatic registration of an MCP resource."""
        res_name = name or uri
        doc = (func.__doc__ or "").strip()
        res_desc = description or doc or f"Resource: {res_name}"

        self._resources[uri] = func
        self._resource_meta[uri] = {
            "uri": uri,
            "name": res_name,
            "description": res_desc,
            "mimeType": mime_type,
        }

    def list_resources(self) -> List[Dict[str, Any]]:
        """Return list of registered MCP resources."""
        return list(self._resource_meta.values())

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read an MCP resource by URI."""
        if uri not in self._resources:
            raise KeyError(f"Resource '{uri}' not found.")

        meta = self._resource_meta[uri]
        func = self._resources[uri]
        
        # Function may take 0 or 1 argument (uri)
        import inspect
        sig = inspect.signature(func)
        if len(sig.parameters) == 1:
            data = func(uri)
        else:
            data = func()

        if isinstance(data, (dict, list)):
            text_data = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            text_data = str(data)

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": meta.get("mimeType", "text/plain"),
                    "text": text_data
                }
            ]
        }

    # ==========================================
    # Prompts API
    # ==========================================

    def prompt(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        arguments: Optional[List[Dict[str, Any]]] = None
    ):
        """Decorator to register a prompt template generator."""
        def decorator(func: Callable):
            self.register_prompt(
                func=func,
                name=name,
                description=description,
                arguments=arguments
            )
            return func
        return decorator

    def register_prompt(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        arguments: Optional[List[Dict[str, Any]]] = None
    ):
        """Programmatic registration of an MCP prompt."""
        prompt_name = name or func.__name__
        doc = (func.__doc__ or "").strip()
        prompt_desc = description or doc or f"Prompt: {prompt_name}"
        args_list = arguments if arguments is not None else function_to_prompt_arguments(func)

        self._prompts[prompt_name] = func
        self._prompt_meta[prompt_name] = {
            "name": prompt_name,
            "description": prompt_desc,
            "arguments": args_list
        }

    def list_prompts(self) -> List[Dict[str, Any]]:
        """Return list of registered MCP prompts."""
        return list(self._prompt_meta.values())

    def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a prompt template and return MCP prompt response."""
        if name not in self._prompts:
            raise KeyError(f"Prompt '{name}' not found.")

        meta = self._prompt_meta[name]
        func = self._prompts[name]
        args = arguments or {}

        res = func(**args)

        # Normalize result into list of messages
        if isinstance(res, list):
            messages = res
        elif isinstance(res, str):
            messages = [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": res
                    }
                }
            ]
        elif isinstance(res, dict) and "messages" in res:
            return res
        else:
            messages = [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": str(res)
                    }
                }
            ]

        return {
            "description": meta.get("description", ""),
            "messages": messages
        }

    # ==========================================
    # JSON-RPC Request Dispatcher
    # ==========================================

    def handle_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a single JSON-RPC 2.0 request."""
        if not isinstance(request_data, dict):
            return make_jsonrpc_error(None, INVALID_REQUEST, "Invalid JSON-RPC request structure.")

        req_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params", {})
        is_notification = (req_id is None)

        if not method or not isinstance(method, str):
            return make_jsonrpc_error(req_id, INVALID_REQUEST, "Missing or invalid 'method' parameter.")

        # 1. Initialize
        if method == METHOD_INITIALIZE:
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version
                }
            }
            return make_jsonrpc_response(req_id, result)

        elif method == METHOD_INITIALIZED:
            return None

        # 2. Ping
        elif method == METHOD_PING:
            return make_jsonrpc_response(req_id, {})

        # 3. Tools
        elif method == METHOD_TOOLS_LIST:
            return make_jsonrpc_response(req_id, {"tools": self.list_tools()})

        elif method == METHOD_TOOLS_CALL:
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not tool_name:
                return make_jsonrpc_error(req_id, INVALID_PARAMS, "Missing required parameter: 'name'")
            if tool_name not in self._tools:
                return make_jsonrpc_error(req_id, METHOD_NOT_FOUND, f"Tool '{tool_name}' not found.")

            res = self.call_tool(tool_name, arguments)
            return make_jsonrpc_response(req_id, res)

        # 4. Resources
        elif method == METHOD_RESOURCES_LIST:
            return make_jsonrpc_response(req_id, {"resources": self.list_resources()})

        elif method == METHOD_RESOURCES_READ:
            uri = params.get("uri")
            if not uri:
                return make_jsonrpc_error(req_id, INVALID_PARAMS, "Missing required parameter: 'uri'")
            if uri not in self._resources:
                return make_jsonrpc_error(req_id, INVALID_PARAMS, f"Resource '{uri}' not found.")

            try:
                res = self.read_resource(uri)
                return make_jsonrpc_response(req_id, res)
            except Exception as e:
                return make_jsonrpc_error(req_id, INTERNAL_ERROR, f"Error reading resource: {str(e)}")

        # 5. Prompts
        elif method == METHOD_PROMPTS_LIST:
            return make_jsonrpc_response(req_id, {"prompts": self.list_prompts()})

        elif method == METHOD_PROMPTS_GET:
            prompt_name = params.get("name")
            arguments = params.get("arguments", {})
            if not prompt_name:
                return make_jsonrpc_error(req_id, INVALID_PARAMS, "Missing required parameter: 'name'")
            if prompt_name not in self._prompts:
                return make_jsonrpc_error(req_id, METHOD_NOT_FOUND, f"Prompt '{prompt_name}' not found.")

            try:
                res = self.get_prompt(prompt_name, arguments)
                return make_jsonrpc_response(req_id, res)
            except Exception as e:
                return make_jsonrpc_error(req_id, INTERNAL_ERROR, f"Error generating prompt: {str(e)}")

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
