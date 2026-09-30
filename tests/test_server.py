"""
Comprehensive unit tests for easy-mcp server, protocol, resources, prompts and tools.
Uses Python standard library unittest (zero external dependencies).
"""

import unittest
from easy_mcp.server import EasyMCP
from easy_mcp.schema import function_to_tool_schema, function_to_prompt_arguments
from easy_mcp.protocol import (
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_PING,
    METHOD_TOOLS_LIST,
    METHOD_TOOLS_CALL,
    METHOD_RESOURCES_LIST,
    METHOD_RESOURCES_READ,
    METHOD_PROMPTS_LIST,
    METHOD_PROMPTS_GET,
    MCP_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    MCPError,
    ParseError,
    InvalidRequestError,
    MethodNotFoundError,
    InvalidParamsError,
    InternalError,
)


class TestEasyMCP(unittest.TestCase):
    def setUp(self):
        self.mcp = EasyMCP(name="test-server", version="0.2.0")

        @self.mcp.tool()
        def greet(name: str, shout: bool = False) -> str:
            """Greet someone.

            Args:
                name: The person's name
                shout: Whether to shout in uppercase
            """
            msg = f"Hello, {name}!"
            return msg.upper() if shout else msg

        @self.mcp.tool()
        def add(a: float, b: float) -> float:
            """Add numbers."""
            return a + b

        @self.mcp.tool()
        def divide(a: float, b: float) -> float:
            """Divide numbers."""
            return a / b

        @self.mcp.resource("memo://system-notes", name="System Notes", description="Internal developer notes")
        def system_notes() -> str:
            return "Server version 0.2.0 running smoothly."

        @self.mcp.resource("file://config.json", mime_type="application/json")
        def config_file() -> dict:
            return {"env": "production", "debug": False}

        @self.mcp.resource("user://profile")
        def user_profile(uri: str) -> str:
            return f"Profile fetched from {uri}"

        @self.mcp.prompt(name="code_review", description="Review code snippet")
        def review_prompt(code: str, language: str = "python") -> str:
            """Review code snippet.

            Args:
                code: Code snippet to analyze
                language: Programming language
            """
            return f"Please review the following {language} code:\n\n{code}"

        @self.mcp.prompt(name="custom_chat")
        def custom_chat_prompt(topic: str):
            return [
                {"role": "user", "content": {"type": "text", "text": f"Tell me about {topic}."}}
            ]

    # ==========================================
    # 1. Schema Generation Tests
    # ==========================================

    def test_schema_generation(self):
        def sample(title: str, count: int = 1) -> str:
            """A sample tool.

            Args:
                title: Title string
                count: Number of times
            """
            return title * count

        schema = function_to_tool_schema(sample)
        self.assertEqual(schema["name"], "sample")
        self.assertIn("A sample tool", schema["description"])
        props = schema["inputSchema"]["properties"]
        self.assertEqual(props["title"]["type"], "string")
        self.assertEqual(props["count"]["type"], "integer")
        self.assertEqual(props["count"]["default"], 1)
        self.assertEqual(schema["inputSchema"]["required"], ["title"])

    def test_prompt_arguments_generation(self):
        def sample_prompt(query: str, limit: int = 10):
            """Sample prompt.

            Args:
                query: Search query
                limit: Max items
            """
            pass

        args = function_to_prompt_arguments(sample_prompt)
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0]["name"], "query")
        self.assertTrue(args[0]["required"])
        self.assertEqual(args[1]["name"], "limit")
        self.assertFalse(args[1]["required"])

    # ==========================================
    # 2. Lifecycle & Initialize Tests
    # ==========================================

    def test_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": METHOD_INITIALIZE,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
        self.assertEqual(res["result"]["serverInfo"]["name"], "test-server")
        caps = res["result"]["capabilities"]
        self.assertIn("tools", caps)
        self.assertIn("resources", caps)
        self.assertIn("prompts", caps)

    def test_initialized_notification(self):
        req = {
            "jsonrpc": "2.0",
            "method": METHOD_INITIALIZED,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        self.assertIsNone(res)

    def test_ping(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": METHOD_PING
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["result"], {})

    # ==========================================
    # 3. Tools Tests
    # ==========================================

    def test_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": METHOD_TOOLS_LIST,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("greet", tool_names)
        self.assertIn("add", tool_names)

    def test_tools_call(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": METHOD_TOOLS_CALL,
            "params": {
                "name": "greet",
                "arguments": {
                    "name": "Claude",
                    "shout": True
                }
            }
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        self.assertFalse(res["result"]["isError"])
        content = res["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["text"], "HELLO, CLAUDE!")

    def test_tools_call_math(self):
        req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": METHOD_TOOLS_CALL,
            "params": {
                "name": "add",
                "arguments": {"a": 10, "b": 25}
            }
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["result"]["content"][0]["text"], "35")

    def test_tools_call_error_handling(self):
        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": METHOD_TOOLS_CALL,
            "params": {
                "name": "divide",
                "arguments": {"a": 10, "b": 0}
            }
        }
        res = self.mcp.handle_request(req)
        self.assertTrue(res["result"]["isError"])
        self.assertIn("division by zero", res["result"]["content"][0]["text"])

    def test_tools_call_missing_name(self):
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": METHOD_TOOLS_CALL,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["error"]["code"], INVALID_PARAMS)

    def test_tools_call_not_found(self):
        req = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": METHOD_TOOLS_CALL,
            "params": {"name": "non_existent_tool"}
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["error"]["code"], METHOD_NOT_FOUND)

    # ==========================================
    # 4. Resources Tests
    # ==========================================

    def test_resources_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": METHOD_RESOURCES_LIST,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        resources = res["result"]["resources"]
        uris = [r["uri"] for r in resources]
        self.assertIn("memo://system-notes", uris)
        self.assertIn("file://config.json", uris)

    def test_resources_read_plain_text(self):
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": METHOD_RESOURCES_READ,
            "params": {"uri": "memo://system-notes"}
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        contents = res["result"]["contents"]
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["uri"], "memo://system-notes")
        self.assertIn("Server version 0.2.0", contents[0]["text"])

    def test_resources_read_json(self):
        req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": METHOD_RESOURCES_READ,
            "params": {"uri": "file://config.json"}
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["result"]["contents"][0]["mimeType"], "application/json")
        self.assertIn('"production"', res["result"]["contents"][0]["text"])

    def test_resources_read_with_uri_arg(self):
        req = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": METHOD_RESOURCES_READ,
            "params": {"uri": "user://profile"}
        }
        res = self.mcp.handle_request(req)
        self.assertIn("Profile fetched from user://profile", res["result"]["contents"][0]["text"])

    def test_resources_read_not_found(self):
        req = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": METHOD_RESOURCES_READ,
            "params": {"uri": "unknown://path"}
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["error"]["code"], INVALID_PARAMS)

    # ==========================================
    # 5. Prompts Tests
    # ==========================================

    def test_prompts_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": METHOD_PROMPTS_LIST,
            "params": {}
        }
        res = self.mcp.handle_request(req)
        prompts = res["result"]["prompts"]
        names = [p["name"] for p in prompts]
        self.assertIn("code_review", names)
        self.assertIn("custom_chat", names)

    def test_prompts_get_str(self):
        req = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": METHOD_PROMPTS_GET,
            "params": {
                "name": "code_review",
                "arguments": {"code": "print('hello')", "language": "python"}
            }
        }
        res = self.mcp.handle_request(req)
        self.assertIsNotNone(res)
        msgs = res["result"]["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertIn("print('hello')", msgs[0]["content"]["text"])

    def test_prompts_get_custom_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 16,
            "method": METHOD_PROMPTS_GET,
            "params": {
                "name": "custom_chat",
                "arguments": {"topic": "Quantum Computing"}
            }
        }
        res = self.mcp.handle_request(req)
        msgs = res["result"]["messages"]
        self.assertIn("Tell me about Quantum Computing.", msgs[0]["content"]["text"])

    def test_prompts_get_not_found(self):
        req = {
            "jsonrpc": "2.0",
            "id": 17,
            "method": METHOD_PROMPTS_GET,
            "params": {"name": "ghost_prompt"}
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["error"]["code"], METHOD_NOT_FOUND)

    # ==========================================
    # 6. General JSON-RPC & Claude Config Tests
    # ==========================================

    def test_unknown_method(self):
        req = {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "invalid/method_name"
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["error"]["code"], METHOD_NOT_FOUND)

    def test_claude_config(self):
        cfg = self.mcp.get_claude_config("/path/to/server.py")
        self.assertIn("mcpServers", cfg)
        self.assertIn("test-server", cfg["mcpServers"])
        self.assertEqual(cfg["mcpServers"]["test-server"]["command"], "python")
        self.assertEqual(cfg["mcpServers"]["test-server"]["args"], ["/path/to/server.py"])

    def test_exception_classes(self):
        err = ParseError("Malformed JSON")
        self.assertEqual(err.code, -32700)
        err2 = MethodNotFoundError()
        self.assertEqual(err2.code, -32601)
        err3 = InvalidParamsError()
        self.assertEqual(err3.code, -32602)
        err4 = InternalError()
        self.assertEqual(err4.code, -32603)
        err5 = InvalidRequestError()
        self.assertEqual(err5.code, -32600)


if __name__ == "__main__":
    unittest.main()
