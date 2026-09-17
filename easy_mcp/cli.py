"""
CLI utilities for easy-mcp.
Scaffold starter servers, generate Claude Desktop config, and test tools locally.
"""

import argparse
import json
import os
import sys

from easy_mcp import __version__

STARTER_TEMPLATE = '''"""
MCP Server generated with easy-mcp.
Connects with Claude Desktop and Claude Code.
"""

from easy_mcp import EasyMCP

mcp = EasyMCP(name="{name}", version="0.1.0", description="Starter MCP Server")


@mcp.tool()
def hello_world(name: str = "World") -> str:
    """Say hello to someone.
    
    Args:
        name: Name of the person to greet
    """
    return f"Hello, {{name}}! Welcome to MCP."


@mcp.tool()
def calculate(expression: str) -> str:
    """Safely calculate a basic arithmetic expression.
    
    Args:
        expression: Simple math expression like '2 + 2 * 10'
    """
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        return "Error: Only basic numbers and operators (+, -, *, /) are allowed."
    try:
        result = eval(expression, {{"__builtins__": None}}, {{}})
        return f"Result: {{result}}"
    except Exception as e:
        return f"Error evaluating expression: {{e}}"


if __name__ == "__main__":
    # If run with --config, prints the Claude Desktop config JSON
    if len(sys.argv) > 1 and sys.argv[1] == "--config":
        mcp.print_claude_config()
    else:
        # Standard MCP stdio mode for Claude Desktop / Claude Code
        mcp.run()
'''


def cmd_init(args: argparse.Namespace) -> int:
    name = args.name or "my-mcp-server"
    filename = args.output or "server.py"

    if os.path.exists(filename) and not args.force:
        print(f"Error: '{filename}' already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    content = STARTER_TEMPLATE.format(name=name)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[easy-mcp] Created starter MCP server: {filename}")
    print(f"\nNext steps:")
    print(f"1. Test your server locally:")
    print(f"   python {filename} --config")
    print(f"2. Add this server to your Claude Desktop config (claude_desktop_config.json)!")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        print(f"Error: Script '{args.script}' not found.", file=sys.stderr)
        return 1

    server_name = os.path.splitext(os.path.basename(script_path))[0]
    cfg = {
        "mcpServers": {
            server_name: {
                "command": "python",
                "args": [script_path]
            }
        }
    }
    print(json.dumps(cfg, indent=2))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="easy-mcp",
        description="Fast, zero-dependency toolkit to build and configure MCP servers for Claude."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Scaffold a new starter MCP server file")
    p_init.add_argument("name", nargs="?", default="my-tools", help="Name of your MCP server")
    p_init.add_argument("-o", "--output", default="server.py", help="Output file path (default: server.py)")
    p_init.add_argument("-f", "--force", action="store_true", help="Overwrite existing file")
    p_init.set_defaults(func=cmd_init)

    # config
    p_cfg = subparsers.add_parser("config", help="Generate Claude Desktop config JSON for an existing script")
    p_cfg.add_argument("script", help="Path to your python MCP server script")
    p_cfg.set_defaults(func=cmd_config)

    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
