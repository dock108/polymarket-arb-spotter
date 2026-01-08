"""
Shared database utilities and common storage helpers.
"""

import sqlite3
from pathlib import Path
from typing import List
from sqlite_utils import Database

def get_db(db_path: str) -> Database:
    """Get a database connection, ensuring parent directory exists."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return Database(db_path)

def get_table_columns(db: Database, table_name: str) -> List[str]:
    """Retrieve column names for a specific table."""
    try:
        return [col[0] for col in db.execute(f"SELECT * FROM {table_name} LIMIT 0").description]
    except Exception:
        return []
