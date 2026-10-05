"""
Claude Desktop 1-Click Installer for EasyMCP.
Auto-detects and updates claude_desktop_config.json safely with backup protection.
Zero external dependencies.
"""

import json
import os
import platform
import shutil
import sys
import time
from typing import Any, Dict, Optional, Tuple


def get_claude_config_path() -> str:
    """Return the absolute path to Claude Desktop configuration file based on OS."""
    system = platform.system()
    if system == "Windows":
        app_data = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        return os.path.join(app_data, "Claude", "claude_desktop_config.json")
    elif system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    else:  # Linux / Unix
        return os.path.expanduser("~/.config/Claude/claude_desktop_config.json")


def install_server(
    script_path: str,
    server_name: Optional[str] = None,
    python_path: Optional[str] = None,
    config_path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    force: bool = False,
) -> Tuple[bool, str]:
    """
    Safely registers an MCP server into Claude Desktop config.

    Args:
        script_path: Path to the python script containing the EasyMCP server.
        server_name: Optional custom server name for mcpServers.
        python_path: Python executable to run the server (defaults to sys.executable).
        config_path: Custom config path (defaults to official Claude Desktop location).
        env: Optional environment variables dictionary.
        force: Replace an existing server of the same name that runs a different script.

    Returns:
        (success: bool, message: str)
    """
    abs_script = os.path.abspath(script_path)
    if not os.path.exists(abs_script):
        return False, f"Server script not found: {script_path}"

    target_name = server_name or os.path.splitext(os.path.basename(abs_script))[0]
    target_name = target_name.replace("_", "-")

    py_exe = python_path or sys.executable
    # Claude Desktop starts servers from its own working directory.
    if os.sep in py_exe or (os.altsep and os.altsep in py_exe):
        py_exe = os.path.abspath(py_exe)
    target_config = config_path or get_claude_config_path()

    config_data: Dict[str, Any] = {"mcpServers": {}}

    if os.path.exists(target_config):
        try:
            # utf-8-sig accepts files saved with a BOM (e.g. by Windows PowerShell 5).
            with open(target_config, "r", encoding="utf-8-sig") as f:
                content = f.read().strip()
            if content:
                config_data = json.loads(content)
        except Exception as e:
            return False, f"Failed to read existing config JSON: {e}"

        if not isinstance(config_data, dict):
            return False, f"Config file is not a JSON object: {target_config}"
        servers = config_data.get("mcpServers")
        if servers is None:
            config_data["mcpServers"] = {}
        elif not isinstance(servers, dict):
            return False, f"'mcpServers' in {target_config} is not a JSON object; fix it by hand first."

        existing = config_data["mcpServers"].get(target_name)
        if isinstance(existing, dict) and existing.get("args") != [abs_script] and not force:
            return False, (
                f"A server named '{target_name}' is already registered "
                f"(args: {existing.get('args')}). Choose another name with --name, "
                f"or use --force to replace it."
            )

        backup_path = f"{target_config}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
        counter = 1
        while os.path.exists(backup_path):
            backup_path = f"{target_config}.{time.strftime('%Y%m%d-%H%M%S')}-{counter}.bak"
            counter += 1
        try:
            shutil.copy2(target_config, backup_path)
        except Exception as e:
            return False, f"Failed to create config backup: {e}"
    else:
        os.makedirs(os.path.dirname(target_config) or ".", exist_ok=True)

    server_entry: Dict[str, Any] = {
        "command": py_exe,
        "args": [abs_script],
    }
    if env:
        server_entry["env"] = env

    config_data["mcpServers"][target_name] = server_entry

    try:
        with open(target_config, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return False, f"Failed to write Claude Desktop config: {e}"

    return True, f"Successfully registered '{target_name}' in Claude Desktop ({target_config})"
