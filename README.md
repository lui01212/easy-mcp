# easy-mcp ⚡🤖

[![PyPI version](https://img.shields.io/pypi/v/easy-mcp.svg)](https://pypi.org/project/easy-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/easy-mcp.svg)](https://pypi.org/project/easy-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/lui01212/easy-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/lui01212/easy-mcp/actions)
[![good first issues](https://img.shields.io/github/issues/lui01212/easy-mcp/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/lui01212/easy-mcp/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**Ultra-lightweight, zero-dependency Python framework for Model Context Protocol (MCP). Build MCP servers for Claude in seconds.**

Turn standard Python functions into Model Context Protocol tools for **Claude Desktop** and **Claude Code** with simple `@mcp.tool()` decorators.

---

## ⚡ Why easy-mcp?

- **Zero dependencies:** Written in 100% pure standard Python. No heavy ASGI servers, no complex async overhead.
- **Pythonic & Simple:** Turn any Python function into an MCP tool with a single decorator `@mcp.tool()`.
- **Automatic Schema Inspection:** Docstrings and type annotations are automatically converted into standard JSON Schemas.
- **Claude Desktop Ready:** Built-in config generator outputs the exact JSON configuration to paste into `claude_desktop_config.json`.
- **Offline & Safe:** Standard I/O (stdio) JSON-RPC 2.0 communication.

---

## 📦 Installation

```bash
pip install easy-mcp
```

---

## 🚀 30-Second Quickstart

### 1. Write your server (`my_tools.py`)

```python
from easy_mcp import EasyMCP

mcp = EasyMCP(name="my-tools", version="1.0.0")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together.
    
    Args:
        a: First number
        b: Second number
    """
    return a + b

@mcp.tool()
def get_system_info() -> dict:
    """Get basic platform system information."""
    import platform
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine()
    }

if __name__ == "__main__":
    mcp.run()
```

### 2. Add to Claude Desktop

Generate the configuration snippet:

```bash
easy-mcp config my_tools.py
```

Output:
```json
{
  "mcpServers": {
    "my-tools": {
      "command": "python",
      "args": [
        "E:\\opensource\\my_tools.py"
      ]
    }
  }
}
```

Paste this into your `claude_desktop_config.json`:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Restart Claude Desktop, and your tools will appear with the 🔨 hammer icon!

---

## 🛠️ CLI Utilities

Scaffold a new server in 1 second:
```bash
easy-mcp init weather-server
```

Generate config for Claude Desktop:
```bash
easy-mcp config server.py
```

---

## 📂 Community MCP Examples (Help Wanted!)

We are building a curated collection of lightweight MCP tool servers in `examples/`:
- `examples/basic_math.py` - Math calculator
- `examples/pii_shield_mcp.py` - AI data privacy sanitizer

### Want to contribute?
Help us add more examples:
- 🌐 SQLite database query tool
- 📰 Hacker News API reader
- 📁 Local markdown note searcher
- ⛅ Weather lookup

See [CONTRIBUTING.md](CONTRIBUTING.md) to submit an example!

---

## 📄 License

[MIT License](LICENSE) © 2026 lui01212
