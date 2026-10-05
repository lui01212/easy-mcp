"""
Regression tests for the 2026-10 audit: stdio transport, schema generation,
the starter template, the installer, the dev CLI and the sqlite example.
"""

import enum
import functools
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import redirect_stderr
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from easy_mcp.cli import main
from easy_mcp.installer import install_server
from easy_mcp.protocol import INTERNAL_ERROR, INVALID_PARAMS
from easy_mcp.schema import function_to_tool_schema, parse_docstring
from easy_mcp.server import EasyMCP

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_server(script_path, messages, env_extra=None, timeout=20):
    """Start a server script over stdio, send JSON-RPC lines, return parsed replies."""
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env.update(env_extra or {})
    payload = "".join(
        (m if isinstance(m, str) else json.dumps(m, ensure_ascii=False)) + "\n" for m in messages
    ).encode("utf-8")
    proc = subprocess.run(
        [sys.executable, script_path],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
    )
    lines = proc.stdout.decode("utf-8").splitlines()
    return proc, [json.loads(line) for line in lines]


class TestStarterTemplate(unittest.TestCase):
    def test_generated_server_runs_over_stdio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "server.py")
            self.assertEqual(main(["init", "it's mine", "-o", script]), 0)

            proc, replies = run_server(script, [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "calculate", "arguments": {"expression": "2 + 3 * 4"}}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "calculate", "arguments": {"expression": "9**9**9**9"}}},
            ])
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "it's mine")
            self.assertEqual(replies[1]["result"]["content"][0]["text"], "Result: 14")
            self.assertIn("Error evaluating expression", replies[2]["result"]["content"][0]["text"])

    def test_generated_server_prints_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "server.py")
            main(["init", "demo", "-o", script])
            env = dict(os.environ, PYTHONPATH=REPO_ROOT)
            proc = subprocess.run(
                [sys.executable, script, "--config"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=20,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            cfg = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(cfg["mcpServers"]["demo"]["command"], sys.executable)


class TestStdioTransport(unittest.TestCase):
    SERVER = textwrap.dedent('''
        from easy_mcp import EasyMCP

        mcp = EasyMCP("stdio-test")

        @mcp.tool()
        def echo(text: str) -> str:
            """Echo text back."""
            print("debug: echo called")
            return text

        @mcp.prompt()
        def unserializable() -> dict:
            """Return messages json cannot encode."""
            return {"messages": [object()]}

        if __name__ == "__main__":
            mcp.run()
    ''')

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.script = os.path.join(self._tmp.name, "srv.py")
        with open(self.script, "w", encoding="utf-8") as f:
            f.write(self.SERVER)

    def tearDown(self):
        self._tmp.cleanup()

    def test_utf8_and_print_do_not_break_the_stream(self):
        # cp1252 is what Windows gives a piped process without UTF-8 mode.
        proc, replies = run_server(self.script, [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "echo", "arguments": {"text": "東京 café"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        ], env_extra={"PYTHONIOENCODING": "cp1252"})
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual([r["id"] for r in replies], [1, 2])
        self.assertEqual(replies[0]["result"]["content"][0]["text"], "東京 café")
        self.assertIn(b"debug: echo called", proc.stderr)

    def test_bad_messages_do_not_kill_the_server(self):
        proc, replies = run_server(self.script, [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": None},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": []},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": ["x"]}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "echo", "arguments": "oops"}},
            {"jsonrpc": "2.0", "id": 5, "method": "prompts/get", "params": {"name": "unserializable"}},
            "{not json",
            {"jsonrpc": "2.0", "method": "ping"},
            {"jsonrpc": "2.0", "id": 6, "method": "ping"},
        ])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        by_id = {r["id"]: r for r in replies}
        self.assertEqual(by_id[1]["error"]["code"], INVALID_PARAMS)
        self.assertEqual(by_id[2]["error"]["code"], INVALID_PARAMS)
        self.assertEqual(by_id[3]["error"]["code"], INVALID_PARAMS)
        self.assertEqual(by_id[4]["error"]["code"], INVALID_PARAMS)
        self.assertEqual(by_id[5]["error"]["code"], INTERNAL_ERROR)
        self.assertEqual(by_id[None]["error"]["code"], -32700)
        self.assertEqual(by_id[6]["result"], {})
        # The id-less ping is a notification: no reply for it.
        self.assertEqual(len(replies), 7)


class TestHandleRequest(unittest.TestCase):
    def setUp(self):
        self.mcp = EasyMCP("t")

        @self.mcp.tool()
        def boom() -> str:
            """Always fails."""
            raise RuntimeError("bad thing")

    def test_notifications_get_no_reply(self):
        for method in ("ping", "tools/list", "tools/call", "unknown/method"):
            self.assertIsNone(self.mcp.handle_request({"jsonrpc": "2.0", "method": method}))

    def test_tool_error_hides_traceback(self):
        with redirect_stderr(io.StringIO()) as err:
            res = self.mcp.call_tool("boom")
        self.assertTrue(res["isError"])
        text = res["content"][0]["text"]
        self.assertIn("RuntimeError: bad thing", text)
        self.assertNotIn("Traceback", text)
        self.assertIn("Traceback", err.getvalue())

    def test_wrapped_async_tool_is_awaited(self):
        async def base(x: int) -> int:
            return x * 2

        @functools.wraps(base)
        def wrapper(*args, **kwargs):
            return base(*args, **kwargs)

        self.mcp.register_tool(wrapper, name="double")
        self.mcp.register_tool(functools.partial(base), name="double_partial")
        self.assertEqual(self.mcp.call_tool("double", {"x": 4})["content"][0]["text"], "8")
        self.assertEqual(self.mcp.call_tool("double_partial", {"x": 5})["content"][0]["text"], "10")


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class Point:
    pass


class TestSchema(unittest.TestCase):
    def props(self, func):
        return function_to_tool_schema(func)["inputSchema"]["properties"]

    def test_generic_types(self):
        def f(a: List[int], b: Dict[str, int], c: List[str], d: Sequence[float],
              e: Optional[List[str]] = None, p: Optional[Point] = None, t: tuple = ()):
            pass

        props = self.props(f)
        self.assertEqual(props["a"], {"type": "array", "items": {"type": "integer"}})
        self.assertEqual(props["b"]["type"], "object")
        self.assertEqual(props["c"], {"type": "array", "items": {"type": "string"}})
        self.assertEqual(props["d"], {"type": "array", "items": {"type": "number"}})
        self.assertEqual(props["e"]["type"], "array")
        self.assertIsNone(props["e"]["default"])
        self.assertEqual(props["p"]["type"], "string")
        self.assertEqual(props["t"]["type"], "array")

    def test_bool_is_not_integer(self):
        def f(flag: bool, n: int):
            pass

        props = self.props(f)
        self.assertEqual(props["flag"]["type"], "boolean")
        self.assertEqual(props["n"]["type"], "integer")

    def test_defaults_are_json_safe(self):
        def paint(color: Color = Color.RED, when: datetime = datetime(2026, 1, 1)):
            pass

        schema = function_to_tool_schema(paint)
        json.dumps(schema)
        props = schema["inputSchema"]["properties"]
        self.assertEqual(props["color"]["default"], "red")
        self.assertNotIn("default", props["when"])

    def test_docstring_sections_do_not_leak_into_params(self):
        desc, params = parse_docstring(textwrap.dedent("""\
            Add two numbers.

            Args:
                a: first
                b: second

            Returns:
                The sum of a and b.

            Raises:
                ValueError: if something is wrong.
        """))
        self.assertEqual(desc, "Add two numbers.")
        self.assertEqual(params, {"a": "first", "b": "second"})


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.script_a = os.path.join(self.dir, "a", "server.py")
        self.script_b = os.path.join(self.dir, "b", "server.py")
        for path in (self.script_a, self.script_b):
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as f:
                f.write("# server\n")
        self.config = os.path.join(self.dir, "claude_desktop_config.json")

    def tearDown(self):
        self._tmp.cleanup()

    def write_config(self, text, encoding="utf-8"):
        with open(self.config, "w", encoding=encoding) as f:
            f.write(text)

    def read_config(self):
        with open(self.config, encoding="utf-8") as f:
            return json.load(f)

    def test_same_name_is_not_overwritten_without_force(self):
        self.assertTrue(install_server(self.script_a, config_path=self.config)[0])
        ok, msg = install_server(self.script_b, config_path=self.config)
        self.assertFalse(ok)
        self.assertIn("--force", msg)
        self.assertEqual(self.read_config()["mcpServers"]["server"]["args"], [os.path.abspath(self.script_a)])

        self.assertTrue(install_server(self.script_b, config_path=self.config, force=True)[0])
        self.assertEqual(self.read_config()["mcpServers"]["server"]["args"], [os.path.abspath(self.script_b)])

    def test_reinstalling_the_same_script_is_allowed(self):
        self.assertTrue(install_server(self.script_a, config_path=self.config)[0])
        self.assertTrue(install_server(self.script_a, config_path=self.config)[0])

    def test_backups_keep_the_original(self):
        self.write_config('{"mcpServers": {"other": {"command": "x"}}}')
        install_server(self.script_a, config_path=self.config)
        install_server(self.script_a, server_name="again", config_path=self.config)
        backups = [n for n in os.listdir(self.dir) if n.endswith(".bak")]
        self.assertEqual(len(backups), 2)
        contents = []
        for name in backups:
            with open(os.path.join(self.dir, name), encoding="utf-8") as f:
                contents.append(json.load(f))
        self.assertIn({"mcpServers": {"other": {"command": "x"}}}, contents)

    def test_bom_config_is_read(self):
        self.write_config('{"mcpServers": {"other": {"command": "x"}}}', encoding="utf-8-sig")
        ok, msg = install_server(self.script_a, config_path=self.config)
        self.assertTrue(ok, msg)
        self.assertIn("other", self.read_config()["mcpServers"])

    def test_invalid_shapes_are_refused_not_rewritten(self):
        for text in ("[]", "null", '{"mcpServers": []}'):
            self.write_config(text)
            ok, _ = install_server(self.script_a, config_path=self.config)
            self.assertFalse(ok, text)
            with open(self.config, encoding="utf-8") as f:
                self.assertEqual(f.read(), text)

    def test_relative_python_path_is_made_absolute(self):
        rel = os.path.join(".venv", "bin", "python")
        install_server(self.script_a, python_path=rel, config_path=self.config)
        self.assertEqual(self.read_config()["mcpServers"]["server"]["command"], os.path.abspath(rel))
        install_server(self.script_a, server_name="bare", python_path="python3", config_path=self.config)
        self.assertEqual(self.read_config()["mcpServers"]["bare"]["command"], "python3")


class TestDevCli(unittest.TestCase):
    def test_unknown_tool_is_a_clean_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["dev", os.path.join(REPO_ROOT, "examples", "basic_math.py"), "--call", "nope"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown tool 'nope'", err.getvalue())


class TestSqliteExample(unittest.TestCase):
    def setUp(self):
        import examples.sqlite_server as sqlite_server
        self.mod = sqlite_server

    def test_with_queries_are_allowed(self):
        rows = self.mod.execute_query("WITH m AS (SELECT name FROM users) SELECT count(*) AS n FROM m")
        self.assertEqual(rows[0]["n"], 2)

    def test_writes_are_rejected(self):
        with self.assertRaises(Exception):
            self.mod.execute_query("WITH x AS (SELECT 1) DELETE FROM users")
        with self.assertRaises(ValueError):
            self.mod.execute_query("DELETE FROM users")
        self.assertEqual(len(self.mod.execute_query("SELECT * FROM users")), 2)

    def test_runaway_query_is_stopped(self):
        old = self.mod.QUERY_TIMEOUT_SECONDS
        self.mod.QUERY_TIMEOUT_SECONDS = 0.5
        try:
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                self.mod.execute_query(
                    "SELECT (WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) "
                    "SELECT count(*) FROM c)"
                )
            self.assertLess(time.monotonic() - start, 5)
        finally:
            self.mod.QUERY_TIMEOUT_SECONDS = old

    def test_describe_table_rejects_unknown_names(self):
        with self.assertRaises(ValueError):
            self.mod.describe_table("users) --")

    def test_file_database_is_read_only(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "data.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            conn.commit()
            conn.close()

            old = self.mod.DB_PATH
            self.mod.DB_PATH = path
            try:
                self.assertEqual(self.mod.execute_query("SELECT x FROM t"), [{"x": 1}])
                with self.assertRaises(sqlite3.Error):
                    self.mod.execute_query("WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a")
                self.mod.DB_PATH = os.path.join(tmpdir, "missing.db")
                with self.assertRaises(FileNotFoundError):
                    self.mod.list_tables()
                self.assertFalse(os.path.exists(os.path.join(tmpdir, "missing.db")))
            finally:
                self.mod.DB_PATH = old


if __name__ == "__main__":
    unittest.main()
