"""SQLite store for students, generated sheets, and practice sessions.

The database is created on first run under the user's data directory.
It is never part of the git repo, so student names stay off GitHub.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def data_dir():
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "easymathbooks"
    return Path.home() / ".local" / "share" / "easymathbooks"


def db_path():
    return data_dir() / "easymath.db"


def default_output_dir():
    return data_dir() / "output"


def _migrate_legacy_db():
    """Keep an existing local DB if the app used to store it in the repo."""
    dest = db_path()
    if dest.exists():
        return
    legacy = ROOT / "data" / "easymath.db"
    if not legacy.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, dest)


def connect():
    _migrate_legacy_db()
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sheets (
                id INTEGER PRIMARY KEY,
                sheet_code TEXT NOT NULL,
                level INTEGER NOT NULL,
                variant INTEGER NOT NULL,
                student_id INTEGER,
                problem_count INTEGER NOT NULL,
                paper TEXT NOT NULL,
                examples INTEGER NOT NULL,
                pdf_path TEXT,
                answers_path TEXT,
                generated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                sheet_code TEXT NOT NULL,
                level INTEGER NOT NULL,
                variant INTEGER NOT NULL,
                taken_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                score INTEGER,
                score_max INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_setting(key, default=None):
    with session() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with session() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def all_settings():
    with session() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def list_students():
    with session() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM students ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def add_student(name):
    name = name.strip()
    if not name:
        raise ValueError("Student name cannot be empty.")
    with session() as conn:
        conn.execute(
            "INSERT INTO students(name, created_at) VALUES(?, ?)",
            (name, now_iso()),
        )
        row = conn.execute(
            "SELECT id, name, created_at FROM students WHERE id = last_insert_rowid()"
        ).fetchone()
    return dict(row)


def rename_student(student_id, name):
    name = name.strip()
    if not name:
        raise ValueError("Student name cannot be empty.")
    with session() as conn:
        conn.execute("UPDATE students SET name = ? WHERE id = ?", (name, student_id))


def delete_student(student_id):
    with session() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


def student_by_id(student_id):
    with session() as conn:
        row = conn.execute(
            "SELECT id, name, created_at FROM students WHERE id = ?", (student_id,)
        ).fetchone()
    return dict(row) if row else None


def record_sheet(sheet_code, level, variant, problem_count, paper, examples,
                 pdf_path, answers_path, student_id=None):
    with session() as conn:
        conn.execute(
            """
            INSERT INTO sheets(
                sheet_code, level, variant, student_id, problem_count,
                paper, examples, pdf_path, answers_path, generated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sheet_code, level, variant, student_id, problem_count,
                paper, int(bool(examples)),
                str(pdf_path) if pdf_path else None,
                str(answers_path) if answers_path else None,
                now_iso(),
            ),
        )


def latest_sheet(sheet_code, student_id=None):
    with session() as conn:
        if student_id is None:
            row = conn.execute(
                "SELECT * FROM sheets WHERE sheet_code = ? ORDER BY id DESC LIMIT 1",
                (sheet_code,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM sheets
                WHERE sheet_code = ? AND (student_id IS ? OR student_id IS NULL)
                ORDER BY (student_id IS NOT ?) DESC, id DESC
                LIMIT 1
                """,
                (sheet_code, student_id, student_id),
            ).fetchone()
    return dict(row) if row else None


def add_session(student_id, sheet_code, level, variant, taken_at,
                duration_seconds, score=None, score_max=None, notes=""):
    if duration_seconds < 0:
        raise ValueError("Duration cannot be negative.")
    if not taken_at:
        taken_at = date.today().isoformat()
    with session() as conn:
        conn.execute(
            """
            INSERT INTO sessions(
                student_id, sheet_code, level, variant, taken_at,
                duration_seconds, score, score_max, notes, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id, sheet_code, level, variant, taken_at,
                int(duration_seconds),
                None if score is None else int(score),
                None if score_max is None else int(score_max),
                (notes or "").strip(),
                now_iso(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = last_insert_rowid()"
        ).fetchone()
    return dict(row)


def delete_session(session_id):
    with session() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def list_sessions(student_id=None, level=None):
    sql = """
        SELECT s.*, st.name AS student_name
        FROM sessions s
        JOIN students st ON st.id = s.student_id
        WHERE 1=1
    """
    params = []
    if student_id is not None:
        sql += " AND s.student_id = ?"
        params.append(student_id)
    if level is not None:
        sql += " AND s.level = ?"
        params.append(level)
    sql += " ORDER BY s.taken_at DESC, s.id DESC"
    with session() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def next_variant(student_id, level):
    """Next unused variant for this student at this level (max used + 1, or 1)."""
    with session() as conn:
        row = conn.execute(
            """
            SELECT MAX(variant) AS v FROM (
                SELECT variant FROM sessions WHERE student_id = ? AND level = ?
                UNION ALL
                SELECT variant FROM sheets WHERE student_id IS ? AND level = ?
            )
            """,
            (student_id, level, student_id, level),
        ).fetchone()
    return (row["v"] or 0) + 1


def level_stats(student_id):
    """Per-level summary used on the Progress tab."""
    with session() as conn:
        rows = conn.execute(
            """
            SELECT
                level,
                COUNT(*) AS sessions,
                MIN(duration_seconds) AS best_seconds,
                MAX(taken_at) AS last_date,
                MIN(taken_at) AS first_date
            FROM sessions
            WHERE student_id = ?
            GROUP BY level
            ORDER BY level
            """,
            (student_id,),
        ).fetchall()
        detail = conn.execute(
            """
            SELECT level, taken_at, duration_seconds, score, score_max, sheet_code
            FROM sessions
            WHERE student_id = ?
            ORDER BY level, taken_at, id
            """,
            (student_id,),
        ).fetchall()
    by_level = {}
    for r in detail:
        by_level.setdefault(r["level"], []).append(dict(r))
    out = []
    for r in rows:
        series = by_level.get(r["level"], [])
        first = series[0] if series else None
        last = series[-1] if series else None
        out.append({
            "level": r["level"],
            "sessions": r["sessions"],
            "best_seconds": r["best_seconds"],
            "first": first,
            "last": last,
            "series": series,
        })
    return out


def format_duration(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
