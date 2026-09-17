"""
Unit tests for easy-mcp server and protocol.
Uses Python's standard library unittest (zero external dependencies).
"""

import unittest
from easy_mcp.server import EasyMCP
from easy_mcp.schema import function_to_tool_schema
from easy_mcp.protocol import (
    METHOD_INITIALIZE,
    METHOD_TOOLS_LIST,
    METHOD_TOOLS_CALL,
    METHOD_PING,
    MCP_PROTOCOL_VERSION,
)


class TestEasyMCP(unittest.TestCase):
    def setUp(self):
        self.mcp = EasyMCP(name="test-server", version="1.0.0")

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

    def test_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
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
            "id": 3,
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
            "id": 4,
            "method": METHOD_TOOLS_CALL,
            "params": {
                "name": "add",
                "arguments": {"a": 10, "b": 25}
            }
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["result"]["content"][0]["text"], "35")

    def test_ping(self):
        req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": METHOD_PING
        }
        res = self.mcp.handle_request(req)
        self.assertEqual(res["result"], {})

    def test_claude_config(self):
        cfg = self.mcp.get_claude_config("/path/to/server.py")
        self.assertIn("mcpServers", cfg)
        self.assertIn("test-server", cfg["mcpServers"])
        self.assertEqual(cfg["mcpServers"]["test-server"]["command"], "python")
        self.assertEqual(cfg["mcpServers"]["test-server"]["args"], ["/path/to/server.py"])


if __name__ == "__main__":
    unittest.main()
