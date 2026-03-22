"""
Executes SQL queries against SQLite databases.
Handles ATTACH DATABASE for cross-database queries.
"""

import sqlite3
import re
import os
from typing import List, Dict, Any, Tuple


def run_query(sql: str, db_config: dict) -> List[Dict[str, Any]]:
    """Execute a SQL query that may span multiple databases.

    Args:
        sql: The full SQL string (may include ATTACH DATABASE statements)
        db_config: Dict with 'primary_db' and 'attach' list

    Returns:
        List of dicts, one per result row, keyed by column name.
    """
    # Use :memory: as the connection and ATTACH all needed databases
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    try:
        # Execute ATTACH statements
        for alias, db_path in db_config.get("attach", []):
            conn.execute(f"ATTACH DATABASE '{db_path}' AS {alias}")

        # Split SQL into statements - separate ATTACHes from the main query
        statements = [s.strip() for s in sql.split(";") if s.strip()]

        # Find the main SELECT statement (skip ATTACH statements)
        select_stmt = None
        for stmt in statements:
            if stmt.upper().startswith("SELECT"):
                select_stmt = stmt
                break
            elif stmt.upper().startswith("ATTACH"):
                # Already handled above, skip
                continue

        if not select_stmt:
            return []

        cursor = conn.execute(select_stmt)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        return [dict(zip(columns, row)) for row in rows]

    finally:
        conn.close()
