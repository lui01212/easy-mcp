# py-easy-mcp ⚡🤖

[![PyPI version](https://img.shields.io/pypi/v/py-easy-mcp.svg)](https://pypi.org/project/py-easy-mcp/)
[![Python versions](https://img.shields.io/pypi/pyversions/py-easy-mcp.svg)](https://pypi.org/project/py-easy-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/lui01212/easy-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/lui01212/easy-mcp/actions)
[![good first issues](https://img.shields.io/github/issues/lui01212/easy-mcp/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/lui01212/easy-mcp/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)
[![Hacktoberfest](https://img.shields.io/badge/Hacktoberfest-2024-ff7a59?logo=hacktoberfest)](https://hacktoberfest.com/)

**Ultra-lightweight, zero-dependency Python framework for Model Context Protocol (MCP). Build MCP servers for Claude in seconds.**

Turn standard Python functions (both sync and `async def`) into Model Context Protocol tools, resources, and prompt templates for **Claude Desktop** and **Claude Code** with simple decorators.

---

## ⚡ Why py-easy-mcp?

- **Zero dependencies:** Written in 100% pure standard Python. Instant startup, zero supply-chain risk.
- **Sync & Async Support:** Supports both standard `def` and modern `async def` tool, resource, and prompt handlers.
- **Full MCP Protocol Support (v0.3.0):** Tools (`@mcp.tool()`), Resources (`@mcp.resource()`), and Prompts (`@mcp.prompt()`).
- **1-Click Claude Desktop Installer:** Run `py-easy-mcp install server.py` to auto-detect and configure `claude_desktop_config.json` with automatic backup.
- **Dev Inspector & Interactive REPL:** Test your tools in the terminal with `py-easy-mcp dev server.py` without needing Claude Desktop open.
- **Automatic Schema Inspection:** Docstrings and type annotations are automatically converted into standard JSON Schemas.
- **Offline & Safe:** Standard I/O (stdio) JSON-RPC 2.0 communication.

---

## 📦 Installation

```bash
pip install py-easy-mcp
```

*(Note: Both CLI commands `py-easy-mcp` and `easy-mcp` are available)*

---

## 🚀 30-Second Quickstart

### 1. Write your server (`my_server.py`)

```python
from easy_mcp import EasyMCP

mcp = EasyMCP(name="my-server", version="0.3.0")

# 1. Register a Sync or Async Tool
@mcp.tool()
async def fetch_weather(city: str) -> dict:
    """Fetch weather forecast for a given city.

    Args:
        city: The city name (e.g. 'Tokyo', 'San Francisco')
    """
    return {"city": city, "temp": "22°C", "condition": "Sunny"}

# 2. Register a Resource (readable context)
@mcp.resource("memo://guidelines")
def guidelines() -> str:
    """Engineering principles."""
    return "1. Keep it simple.\n2. Zero external dependencies.\n3. Write clear tests."

# 3. Register a Prompt Template
@mcp.prompt()
def code_review(code: str, language: str = "python") -> str:
    """Review code for bugs and maintainability."""
    return f"Please review this {language} snippet:\n\n{code}"

if __name__ == "__main__":
    mcp.run()
```

### 2. 1-Click Install to Claude Desktop

Simply run:

```bash
py-easy-mcp install my_server.py
```

`py-easy-mcp` will:
1. Locate your OS Claude config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/...` on macOS).
2. Create a timestamped backup (`claude_desktop_config.json.bak`).
3. Register `my-server` pointing to your current Python environment.

Restart Claude Desktop, and your tools will appear instantly!

---

## 🛠️ CLI Utilities & Dev Tools

### Dev Inspector (Offline Testing)
Inspect all registered schemas, parameter requirements, and docstrings:
```bash
py-easy-mcp dev my_server.py
```

### Direct Tool Execution
Test a tool directly from your command line:
```bash
py-easy-mcp dev my_server.py --call fetch_weather -a '{"city": "Tokyo"}'
```

### Interactive REPL
Start an interactive terminal session to explore tools and resources:
```bash
py-easy-mcp dev my_server.py -i
```

### Scaffold a New Project
```bash
py-easy-mcp init weather-server
```

---

## 📂 Production MCP Examples

Check out our ready-to-run examples in `examples/`:
- `examples/sqlite_server.py` - Full SQLite database inspector with `list_tables`, `describe_table`, `execute_query` (read-only), and schema DDL resource.
- `examples/basic_math.py` - Arithmetic calculation tools.
- `examples/pii_shield_mcp.py` - AI data privacy sanitizer for Claude.

---

## 🤝 Contributing for Hacktoberfest

We welcome beginner-friendly contributions! Add new lightweight tool examples or protocol extensions. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

---

## 📄 License

[MIT License](LICENSE) © 2026 lui01212
