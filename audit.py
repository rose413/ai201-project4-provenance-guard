"""
Audit log — SQLite-backed persistence for all submission and appeal events.

Schema
------
submissions
    content_id       TEXT  PRIMARY KEY
    creator_id       TEXT  NOT NULL
    timestamp        TEXT  NOT NULL  (ISO-8601 UTC, e.g. 2025-04-01T14:32:10.123Z)
    llm_score        REAL            (Signal 1 — filled at submission time)
    stylometric_score REAL           (Signal 2 — filled in Milestone 4)
    confidence       REAL            (Confidence Engine — filled in Milestone 4)
    attribution      TEXT            (Label string — filled in Milestone 5)
    status           TEXT  NOT NULL  ('classified' | 'under_review' | 'resolved')
    appeal_reason    TEXT            (filled by POST /appeal in Milestone 5)

appeals — added in Milestone 5; declared here so the schema is complete.
"""

import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "audit.db")


def init_db() -> None:
    """Create tables if they do not yet exist. Safe to call on every startup."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                content_id        TEXT PRIMARY KEY,
                creator_id        TEXT NOT NULL,
                timestamp         TEXT NOT NULL,
                llm_score         REAL,
                stylometric_score REAL,
                confidence        REAL,
                attribution       TEXT,
                status            TEXT NOT NULL DEFAULT 'classified',
                appeal_reason     TEXT
            )
        """)
        conn.commit()


def log_submission(
    content_id: str,
    creator_id: str,
    timestamp: str,
    llm_score: float,
    stylometric_score: Optional[float] = None,
    confidence: Optional[float] = None,
    attribution: Optional[str] = None,
    status: str = "classified",
) -> None:
    """Insert a new submission row into the audit log."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO submissions
                (content_id, creator_id, timestamp, llm_score,
                 stylometric_score, confidence, attribution, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (content_id, creator_id, timestamp, llm_score,
             stylometric_score, confidence, attribution, status),
        )
        conn.commit()


def get_submission(content_id: str) -> Optional[dict]:
    """Return a submission row as a dict, or None if not found."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM submissions WHERE content_id = ?", (content_id,)
        ).fetchone()
    return dict(row) if row else None


def get_log(limit: int = 20) -> list:
    """Return the most recent *limit* submission rows as a list of dicts."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def update_submission(content_id: str, **fields) -> None:
    """
    Patch arbitrary columns on an existing row.

    Example:
        update_submission(content_id, status="under_review", appeal_reason="...")
    """
    if not fields:
        return
    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [content_id]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"UPDATE submissions SET {set_clause} WHERE content_id = ?",
            values,
        )
        conn.commit()
