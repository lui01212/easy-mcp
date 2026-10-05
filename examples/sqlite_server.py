"""
SQLite Database MCP Server.
Allows Claude Desktop to inspect database schemas, read tables, and run read-only queries.
Built with easy-mcp (zero external dependencies, uses Python standard library sqlite3).
"""

import os
import pathlib
import sqlite3
import time
from typing import Any, Dict, List, Optional
from easy_mcp import EasyMCP

mcp = EasyMCP(
    name="sqlite-mcp-server",
    version="0.3.1",
    description="Inspect and query SQLite databases from Claude Desktop"
)

# In-memory demo DB with sample tables if no custom DB path is set
DB_PATH = os.environ.get("SQLITE_DB_PATH", ":memory:")
QUERY_TIMEOUT_SECONDS = 5.0
MAX_ROWS = 1000
_shared_conn: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _shared_conn
    if DB_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
        return _shared_conn
    path = pathlib.Path(DB_PATH).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"SQLITE_DB_PATH does not exist: {path}")
    # mode=ro opens the file read-only; query_only also rejects writes at the SQL level.
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _run(conn: sqlite3.Connection, sql: str, params: tuple = (), limit: Optional[int] = None) -> List[sqlite3.Row]:
    """Run one statement, aborting it once QUERY_TIMEOUT_SECONDS has passed."""
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(sql, params)
        return cur.fetchall() if limit is None else cur.fetchmany(limit)
    except sqlite3.OperationalError as e:
        if str(e) == "interrupted":
            raise TimeoutError(f"Query stopped after {QUERY_TIMEOUT_SECONDS:g} seconds.") from e
        raise
    finally:
        conn.set_progress_handler(None, 0)


def close_db(conn: sqlite3.Connection) -> None:
    if conn is not _shared_conn:
        conn.close()


# Initialize sample data if in-memory
if DB_PATH == ":memory:":
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'developer'
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT OR IGNORE INTO users (name, email, role) VALUES
            ('Alice Smith', 'alice@company.com', 'maintainer'),
            ('Bob Jones', 'bob@company.com', 'contributor');
        INSERT OR IGNORE INTO projects (user_id, title, status) VALUES
            (1, 'commit-shield', 'active'),
            (1, 'pii-masker-ai', 'active'),
            (2, 'easy-mcp', 'active');
    """)
    conn.commit()
    conn.execute("PRAGMA query_only = ON")


@mcp.tool()
def list_tables() -> List[str]:
    """List all table names present in the SQLite database."""
    conn = get_db()
    try:
        rows = _run(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        return [row[0] for row in rows]
    finally:
        close_db(conn)


@mcp.tool()
def describe_table(table_name: str) -> List[Dict[str, Any]]:
    """Get the schema definition and column types of a database table.
    
    Args:
        table_name: Name of the table to inspect
    """
    if table_name not in list_tables():
        raise ValueError(f"Unknown table: {table_name!r}")
    conn = get_db()
    try:
        columns = []
        for row in _run(conn, "SELECT * FROM pragma_table_info(?)", (table_name,)):
            columns.append({
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "primary_key": bool(row["pk"])
            })
        return columns
    finally:
        close_db(conn)


@mcp.tool()
def execute_query(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Execute a read-only SELECT SQL query and return rows as dictionaries.
    
    Args:
        query: The SELECT (or WITH ... SELECT) query to run (e.g. 'SELECT * FROM users LIMIT 10')
        limit: Maximum number of rows to return (default 50, at most 1000)
    """
    clean_sql = query.strip()
    first_word = clean_sql.split(None, 1)[0].upper() if clean_sql else ""
    if first_word not in ("SELECT", "WITH"):
        raise ValueError("Only SELECT queries are permitted.")
    limit = max(1, min(int(limit), MAX_ROWS))

    conn = get_db()
    try:
        return [dict(row) for row in _run(conn, clean_sql, limit=limit)]
    finally:
        close_db(conn)


@mcp.resource("sqlite://schema")
def database_schema() -> str:
    """Complete SQLite database DDL schema."""
    conn = get_db()
    try:
        ddls = [row[0] for row in _run(conn, "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL;")]
        return "\n\n".join(ddls)
    finally:
        close_db(conn)


@mcp.prompt()
def sql_assistant(task: str) -> str:
    """Prompt template instructing Claude to act as an expert SQLite data analyst.
    
    Args:
        task: Business question or data retrieval request
    """
    return (
        f"You are an expert SQLite DBA and data analyst.\n"
        f"Use the available tools (`list_tables`, `describe_table`, `execute_query`) "
        f"to examine the schema and answer the following request:\n\n"
        f"User Request: {task}"
    )


if __name__ == "__main__":
    mcp.run()
