"""SQLite helpers + backfill_state bookkeeping for resumable backfills."""
import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def state_keys(conn: sqlite3.Connection, task: str, statuses=("done",)) -> set[str]:
    """Keys of work units already in one of the given states for a task."""
    qmarks = ",".join("?" * len(statuses))
    rows = conn.execute(
        f"SELECT key FROM backfill_state WHERE task = ? AND status IN ({qmarks})",
        (task, *statuses),
    )
    return {r[0] for r in rows}


def set_state(conn: sqlite3.Connection, task: str, key: str, status: str, detail: str | None = None):
    conn.execute(
        """INSERT INTO backfill_state (task, key, status, detail, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(task, key) DO UPDATE SET
               status = excluded.status,
               detail = excluded.detail,
               updated_at = excluded.updated_at""",
        (task, key, status, detail),
    )
