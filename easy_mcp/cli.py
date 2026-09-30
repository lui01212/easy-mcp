"""
CLI utilities for easy-mcp.
Scaffold starter servers, 1-click install into Claude Desktop, inspect tools, and test execution.
"""

import argparse
import json
import os
import sys

from easy_mcp import __version__
from easy_mcp.installer import install_server, get_claude_config_path
from easy_mcp.dev import load_server_from_file, format_server_summary, run_interactive_repl

STARTER_TEMPLATE = '''"""
MCP Server generated with easy-mcp.
Connects with Claude Desktop and Claude Code.
"""

from easy_mcp import EasyMCP

mcp = EasyMCP(name="{name}", version="0.3.0", description="Starter MCP Server")


@mcp.tool()
def hello_world(name: str = "World") -> str:
    \"\"\"Say hello to someone.
    
    Args:
        name: Name of the person to greet
    \"\"\"
    return f"Hello, {{name}}! Welcome to MCP."


@mcp.tool()
def calculate(expression: str) -> str:
    \"\"\"Safely calculate a basic arithmetic expression.
    
    Args:
        expression: Simple math expression like '2 + 2 * 10'
    \"\"\"
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
    print(f"1. Test tools locally:")
    print(f"   easy-mcp dev {filename}")
    print(f"2. 1-Click install into Claude Desktop:")
    print(f"   easy-mcp install {filename}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        print(f"Error: Script '{args.script}' not found.", file=sys.stderr)
        return 1

    server_name = os.path.splitext(os.path.basename(script_path))[0].replace("_", "-")
    cfg = {
        "mcpServers": {
            server_name: {
                "command": sys.executable,
                "args": [script_path]
            }
        }
    }
    print(json.dumps(cfg, indent=2))
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """1-Click installer into Claude Desktop."""
    success, msg = install_server(
        script_path=args.script,
        server_name=args.name,
        python_path=args.python,
        config_path=args.config,
    )
    if success:
        print(f"[OK] {msg}")
        print("Restart Claude Desktop to use your new tools!")
        return 0
    else:
        print(f"Error: {msg}", file=sys.stderr)
        return 1


def cmd_dev(args: argparse.Namespace) -> int:
    """Inspect and test an MCP server without Claude Desktop."""
    try:
        mcp = load_server_from_file(args.script)
    except Exception as e:
        print(f"Error loading server from '{args.script}': {e}", file=sys.stderr)
        return 1

    if args.call:
        tool_name = args.call
        arguments = {}
        if args.args:
            try:
                arguments = json.loads(args.args)
            except Exception as e:
                print(f"Error: Invalid JSON arguments: {e}", file=sys.stderr)
                return 1
        res = mcp.call_tool(tool_name, arguments)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    if args.interactive:
        run_interactive_repl(mcp)
        return 0

    # Default: print inspector summary
    print(format_server_summary(mcp))
    print("\nTip: Run with -i for interactive REPL or --call <tool> -a '{\"arg\": 1}' to test tool execution.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="easy-mcp",
        description="Fast, zero-dependency toolkit to build, test, and install MCP servers for Claude."
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
    p_cfg = subparsers.add_parser("config", help="Generate Claude Desktop config JSON snippet")
    p_cfg.add_argument("script", help="Path to your python MCP server script")
    p_cfg.set_defaults(func=cmd_config)

    # install
    p_inst = subparsers.add_parser("install", help="1-Click install MCP server into Claude Desktop config")
    p_inst.add_argument("script", help="Path to your python MCP server script")
    p_inst.add_argument("-n", "--name", help="Custom server name in Claude config")
    p_inst.add_argument("-p", "--python", help="Path to Python interpreter (defaults to current python)")
    p_inst.add_argument("-c", "--config", help="Custom claude_desktop_config.json path")
    p_inst.set_defaults(func=cmd_install)

    # dev
    p_dev = subparsers.add_parser("dev", help="Inspect schemas and test tools in terminal")
    p_dev.add_argument("script", help="Path to your python MCP server script")
    p_dev.add_argument("--call", help="Tool name to call directly")
    p_dev.add_argument("-a", "--args", help="JSON string of arguments for the tool call")
    p_dev.add_argument("-i", "--interactive", action="store_true", help="Launch interactive dev REPL")
    p_dev.set_defaults(func=cmd_dev)

    args = parser.parse_args(argv)
    if not args.subcommand:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
