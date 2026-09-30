"""
Terminal Dev Inspector and Interactive REPL for EasyMCP servers.
Inspects schemas, tools, resources, and tests execution without Claude Desktop.
Zero external dependencies.
"""

import importlib.util
import json
import os
import sys
from typing import Any, Dict, Optional

from easy_mcp.server import EasyMCP


def load_server_from_file(script_path: str) -> EasyMCP:
    """Dynamically load an EasyMCP instance from a Python script."""
    abs_path = os.path.abspath(script_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Server script not found: {script_path}")

    module_name = f"mcp_server_module_{os.path.splitext(os.path.basename(abs_path))[0]}"
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load module specification from: {abs_path}")

    module = importlib.util.module_from_spec(spec)
    # Add script dir to sys.path temporarily so relative imports resolve
    script_dir = os.path.dirname(abs_path)
    inserted_path = False
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        inserted_path = True

    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_path and sys.path[0] == script_dir:
            sys.path.pop(0)

    # Search for EasyMCP instance in module attributes
    for val in module.__dict__.values():
        if isinstance(val, EasyMCP):
            return val

    raise ValueError(f"No EasyMCP instance found in '{script_path}'. Did you define mcp = EasyMCP(...) ?")


def format_server_summary(mcp: EasyMCP) -> str:
    """Format human-readable inspector summary of tools, resources, and prompts."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  EasyMCP Dev Inspector: {mcp.name} (v{mcp.version})")
    if mcp.description:
        lines.append(f"  {mcp.description}")
    lines.append("=" * 60)

    # Tools
    tools = mcp.list_tools()
    lines.append(f"\n[Tools ({len(tools)})]")
    if not tools:
        lines.append("  (None registered)")
    else:
        for t in tools:
            lines.append(f"\n* {t['name']}")
            if t.get("description"):
                lines.append(f"  Description: {t['description']}")
            schema = t.get("inputSchema", {})
            properties = schema.get("properties", {})
            required = set(schema.get("required", []))
            if properties:
                lines.append("  Parameters:")
                for param, pmeta in properties.items():
                    req_mark = "(required)" if param in required else "(optional)"
                    p_type = pmeta.get("type", "any")
                    p_desc = f" - {pmeta['description']}" if "description" in pmeta else ""
                    lines.append(f"    - {param}: {p_type} {req_mark}{p_desc}")
            else:
                lines.append("  Parameters: None")

    # Resources
    resources = mcp.list_resources()
    lines.append(f"\n[Resources ({len(resources)})]")
    if not resources:
        lines.append("  (None registered)")
    else:
        for r in resources:
            lines.append(f"* {r['uri']} [{r.get('mimeType', 'text/plain')}]")
            if r.get("description"):
                lines.append(f"  Description: {r['description']}")

    # Prompts
    prompts = mcp.list_prompts()
    lines.append(f"\n[Prompts ({len(prompts)})]")
    if not prompts:
        lines.append("  (None registered)")
    else:
        for p in prompts:
            lines.append(f"* {p['name']}")
            if p.get("description"):
                lines.append(f"  Description: {p['description']}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def run_interactive_repl(mcp: EasyMCP) -> None:
    """Interactive dev REPL for testing MCP tools in the console."""
    print("\nEntering EasyMCP Interactive REPL (type 'help' or 'exit').")
    print("Commands: tools | call <tool_name> [json_args] | resources | read <uri> | exit")

    while True:
        try:
            line = input("\neasy-mcp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting REPL.")
            break

        if not line:
            continue
        if line in ["exit", "quit", "q"]:
            break
        elif line == "help":
            print("Available commands:")
            print("  tools                     - List all tools with signatures")
            print("  call <tool> [json_args]   - Execute a tool with optional JSON arguments")
            print("  resources                 - List all resources")
            print("  read <uri>                - Read content of a resource URI")
            print("  prompts                   - List all prompt templates")
            print("  exit                      - Exit REPL")
            continue
        elif line in ["tools", "list"]:
            for t in mcp.list_tools():
                print(f"- {t['name']}: {t.get('description', '')}")
            continue
        elif line == "resources":
            for r in mcp.list_resources():
                print(f"- {r['uri']}: {r.get('description', '')}")
            continue
        elif line == "prompts":
            for p in mcp.list_prompts():
                print(f"- {p['name']}: {p.get('description', '')}")
            continue

        parts = line.split(None, 2)
        cmd = parts[0].lower()

        if cmd == "call":
            if len(parts) < 2:
                print("Usage: call <tool_name> [json_args]")
                continue
            tool_name = parts[1]
            args: Dict[str, Any] = {}
            if len(parts) > 2:
                try:
                    args = json.loads(parts[2])
                except Exception as e:
                    print(f"Error parsing JSON arguments: {e}")
                    continue
            res = mcp.call_tool(tool_name, args)
            print(json.dumps(res, indent=2, ensure_ascii=False))

        elif cmd == "read":
            if len(parts) < 2:
                print("Usage: read <uri>")
                continue
            try:
                res = mcp.read_resource(parts[1])
                print(json.dumps(res, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Error reading resource: {e}")

        else:
            print(f"Unknown command: '{cmd}'. Type 'help' for command list.")
