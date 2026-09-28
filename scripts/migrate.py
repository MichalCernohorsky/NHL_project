#!/usr/bin/env python3
"""Apply versioned SQL migrations from migrations/ to the SQLite database.

Each migration runs exactly once, inside a transaction, in filename order.
Applied versions are recorded in schema_migrations, so re-running the script
is a no-op (idempotent).

Usage:
    python scripts/migrate.py            # apply pending migrations
    python scripts/migrate.py --status   # show applied/pending
    python scripts/migrate.py --schema   # dump current DB schema
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nhl_tool.config import load_config, resolve_db_path
from nhl_tool.db import connect

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def ensure_migrations_table(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version    TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    conn.commit()


def applied_versions(conn):
    return {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}


def migration_files():
    return sorted(MIGRATIONS_DIR.glob("[0-9]*.sql"))


def apply_migrations(conn):
    done = applied_versions(conn)
    applied = 0
    for path in migration_files():
        version = path.stem
        if version in done:
            continue
        sql = path.read_text()
        try:
            conn.executescript("BEGIN;\n" + sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            conn.commit()
        except Exception:
            conn.rollback()
            print(f"FAILED: {version}", file=sys.stderr)
            raise
        print(f"applied: {version}")
        applied += 1
    if applied == 0:
        print("database is up to date")


def show_status(conn):
    done = applied_versions(conn)
    for path in migration_files():
        mark = "applied" if path.stem in done else "PENDING"
        print(f"{mark:8s} {path.stem}")


def dump_schema(conn):
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"
        " AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name"
    )
    for (sql,) in rows:
        print(sql.rstrip() + ";\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--schema", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    conn = connect(resolve_db_path(cfg))
    ensure_migrations_table(conn)

    if args.status:
        show_status(conn)
    elif args.schema:
        dump_schema(conn)
    else:
        apply_migrations(conn)


if __name__ == "__main__":
    main()
