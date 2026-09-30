"""
SQLite Database MCP Server.
Allows Claude Desktop to inspect database schemas, read tables, and run read-only queries.
Built with easy-mcp (zero external dependencies, uses Python standard library sqlite3).
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional
from easy_mcp import EasyMCP

mcp = EasyMCP(
    name="sqlite-mcp-server",
    version="0.3.0",
    description="Inspect and query SQLite databases from Claude Desktop"
)

# In-memory demo DB with sample tables if no custom DB path is set
DB_PATH = os.environ.get("SQLITE_DB_PATH", ":memory:")
_shared_conn: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _shared_conn
    if DB_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _shared_conn.row_factory = sqlite3.Row
        return _shared_conn
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


@mcp.tool()
def list_tables() -> List[str]:
    """List all table names present in the SQLite database."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        return [row[0] for row in cur.fetchall()]
    finally:
        close_db(conn)


@mcp.tool()
def describe_table(table_name: str) -> List[Dict[str, Any]]:
    """Get the schema definition and column types of a database table.
    
    Args:
        table_name: Name of the table to inspect
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name});")
        columns = []
        for row in cur.fetchall():
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
        query: The SELECT query to run (e.g. 'SELECT * FROM users LIMIT 10')
        limit: Maximum number of rows to return (default 50)
    """
    clean_sql = query.strip()
    if not clean_sql.upper().startswith("SELECT"):
        raise ValueError("Security violation: Only SELECT queries are permitted.")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(clean_sql)
        rows = cur.fetchmany(limit)
        return [dict(row) for row in rows]
    finally:
        close_db(conn)


@mcp.resource("sqlite://schema")
def database_schema() -> str:
    """Complete SQLite database DDL schema."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL;")
        ddls = [row[0] for row in cur.fetchall()]
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
