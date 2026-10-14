"""SQLite store for students, generated sheets, and practice sessions.

The database is created on first run under the user's data directory.
It is never part of the git repo, so student names stay off GitHub.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
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
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
        additions = {"gender": "TEXT", "motif": "TEXT",
                     "show_timing": "INTEGER NOT NULL DEFAULT 0",
                     "themed_sheets": "INTEGER NOT NULL DEFAULT 0",
                     "weekly_reminder": "INTEGER NOT NULL DEFAULT 0",
                     "missed_reminder": "INTEGER NOT NULL DEFAULT 0",
                     "notification_consent": "INTEGER NOT NULL DEFAULT 0",
                     "missed_days": "INTEGER NOT NULL DEFAULT 3",
                     "reminder_time": "TEXT NOT NULL DEFAULT '18:00'"}
        for column, definition in additions.items():
            if column not in columns:
                conn.execute(f"ALTER TABLE students ADD COLUMN {column} {definition}")
        conn.execute("""CREATE TABLE IF NOT EXISTS reminder_deliveries (
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            kind TEXT NOT NULL, period TEXT NOT NULL,
            PRIMARY KEY(student_id, kind, period))""")


MOTIFS = {
    "female": ("flowers", "unicorns", "butterflies"),
    "male": ("sports", "cars", "airplanes"),
}


def validate_profile(gender, motif):
    if gender not in MOTIFS:
        raise ValueError("Choose Male or Female.")
    if motif not in MOTIFS[gender]:
        raise ValueError("Choose a motif for the selected gender.")


def update_student(student_id, name, gender, motif):
    validate_profile(gender, motif)
    name = name.strip()
    if not name:
        raise ValueError("Student name cannot be empty.")
    with session() as conn:
        result = conn.execute(
            "UPDATE students SET name = ?, gender = ?, motif = ? WHERE id = ?",
            (name, gender, motif, student_id),
        )
        if not result.rowcount:
            raise ValueError("Student not found.")
    return student_by_id(student_id)


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
            "SELECT * FROM students ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(r) for r in rows]


def add_student(name, gender=None, motif=None):
    if gender is not None or motif is not None:
        validate_profile(gender, motif)
    name = name.strip()
    if not name:
        raise ValueError("Student name cannot be empty.")
    with session() as conn:
        conn.execute(
            "INSERT INTO students(name, gender, motif, created_at) VALUES(?, ?, ?, ?)",
            (name, gender, motif, now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM students WHERE id = last_insert_rowid()"
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
            "SELECT * FROM students WHERE id = ?", (student_id,)
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
    if not student_id:
        return 1
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


def student_progress_pointer(student_id):
    """Highest level this student has used, and the next seed to generate there."""
    if not student_id:
        return {"level": 1, "variant": 1}
    with session() as conn:
        sess_level = conn.execute(
            "SELECT MAX(level) AS level FROM sessions WHERE student_id = ?",
            (student_id,),
        ).fetchone()["level"]
        sheet_level = conn.execute(
            "SELECT MAX(level) AS level FROM sheets WHERE student_id IS ?",
            (student_id,),
        ).fetchone()["level"]
    # Finished sessions are where the student is. Generated-only sheets
    # only set the level when nothing has been timed yet.
    level = sess_level or sheet_level or 1
    return {"level": int(level), "variant": next_variant(student_id, int(level))}


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
            SELECT level, variant, taken_at, duration_seconds, score, score_max, sheet_code
            FROM sessions
            WHERE student_id = ?
            ORDER BY level, variant, id
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


WEEKDAY_LETTERS = "MTWTFSS"
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def empty_report():
    return {
        "has_data": False,
        "session_count": 0,
        "first_date": None,
        "today_count": 0,
        "week_count": 0,
        "week_skipped": 0,
        "range_skipped": 0,
        "range_practiced": 0,
        "streak": 0,
        "accuracy_pct": None,
        "correct": 0,
        "possible": 0,
        "headline": "Save a practice session to see statistics.",
        "days": [],
        "week_days": [],
        "weeks": [],
        "levels": [],
        "max_day": 0,
        "max_week": 0,
    }


def _day_counts(sessions):
    counts = {}
    for row in sessions:
        day = _as_date(row["taken_at"])
        counts[day] = counts.get(day, 0) + 1
    return counts


def _accuracy(sessions):
    correct = 0
    possible = 0
    for row in sessions:
        score = row.get("score")
        score_max = row.get("score_max")
        if score is None or score_max is None or int(score_max) <= 0:
            continue
        correct += int(score)
        possible += int(score_max)
    pct = round(100.0 * correct / possible, 1) if possible else None
    return correct, possible, pct


def _problem_count(row):
    n = row.get("score_max")
    if n is None:
        return None
    n = int(n)
    return n if n > 0 else None


def seconds_per_exercise(row):
    """Wall time divided by problems on that page (example sheets have fewer)."""
    n = _problem_count(row)
    if not n:
        return None
    return int(row.get("duration_seconds") or 0) / n


def format_per_exercise(seconds):
    if seconds is None:
        return "—"
    seconds = max(0.0, float(seconds))
    if seconds >= 60:
        return f"{format_duration(int(round(seconds)))} / exercise"
    if abs(seconds - round(seconds)) < 0.05:
        return f"{int(round(seconds))}s / exercise"
    return f"{seconds:.1f}s / exercise"


def _pace(series):
    rates = []
    for row in series:
        each = seconds_per_exercise(row)
        if each is None:
            continue
        rates.append((row, each))
    if not rates:
        times = [int(row["duration_seconds"] or 0) for row in series]
        first_t = times[0]
        last_t = times[-1]
        best_t = min(times)
        values = times
        unit_first, unit_last, unit_best = first_t, last_t, best_t
        per_exercise = False
    else:
        values = [each for _, each in rates]
        first_t = int(rates[0][0]["duration_seconds"] or 0)
        last_t = int(rates[-1][0]["duration_seconds"] or 0)
        best_t = min(int(row["duration_seconds"] or 0) for row, _ in rates)
        unit_first, unit_last, unit_best = values[0], values[-1], min(values)
        per_exercise = True

    delta = unit_first - unit_last
    if unit_first > 0 and len(values) >= 2:
        faster_pct = int(round(100.0 * delta / unit_first))
    else:
        faster_pct = 0

    def label(seconds):
        return format_per_exercise(seconds) if per_exercise else format_duration(int(round(seconds)))

    if len(values) < 2:
        trend = "new"
        pace_label = label(unit_first)
    elif unit_last < unit_first:
        trend = "faster"
        pace_label = f"{label(unit_first)} → {label(unit_last)} · {abs(faster_pct)}% faster"
    elif unit_last > unit_first:
        trend = "slower"
        pace_label = f"{label(unit_first)} → {label(unit_last)} · {abs(faster_pct)}% slower"
    else:
        trend = "steady"
        pace_label = f"steady at {label(unit_last)}"

    mx = max(values) or 1
    spark = []
    source = rates[-16:] if per_exercise else [(row, int(row["duration_seconds"] or 0)) for row in series[-16:]]
    for row, value in source:
        spark.append({
            "sheet_code": row["sheet_code"],
            "taken_at": str(row["taken_at"])[:10],
            "duration_seconds": int(row["duration_seconds"] or 0),
            "problems": _problem_count(row),
            "seconds_each": round(value, 3),
            "height": round(0.18 + 0.82 * (value / mx), 3),
            "score": row.get("score"),
            "score_max": row.get("score_max"),
        })
    return {
        "first_seconds": first_t,
        "last_seconds": last_t,
        "best_seconds": best_t,
        "first_each": round(unit_first, 3) if per_exercise else None,
        "last_each": round(unit_last, 3) if per_exercise else None,
        "best_each": round(unit_best, 3) if per_exercise else None,
        "best_pace_label": label(unit_best),
        "delta_seconds": delta,
        "faster_pct": faster_pct,
        "trend": trend,
        "pace_label": pace_label,
        "spark": spark,
    }


def progress_report(student_id, today=None, sessions=None):
    """Statistics for the Progress tab: volume, skips, accuracy, speed."""
    today = today or date.today()
    if not student_id:
        return empty_report()
    if sessions is None:
        sessions = list_sessions(student_id)
    chrono = sorted(sessions, key=lambda row: (str(row["taken_at"]), row["id"]))
    if not chrono:
        return empty_report()

    counts = _day_counts(chrono)
    first_date = _as_date(chrono[0]["taken_at"])
    week_start = today - timedelta(days=today.weekday())
    range_start = today - timedelta(days=13)

    def describe_day(day):
        count = counts.get(day, 0)
        before = day < first_date
        future = day > today
        skipped = (not before) and (not future) and count == 0
        return {
            "date": day.isoformat(),
            "letter": WEEKDAY_LETTERS[day.weekday()],
            "weekday": WEEKDAY_NAMES[day.weekday()],
            "count": count,
            "skipped": skipped,
            "before_start": before,
            "future": future,
        }

    days = [describe_day(range_start + timedelta(days=i)) for i in range(14)]
    week_days = [describe_day(week_start + timedelta(days=i)) for i in range(7)]
    today_count = counts.get(today, 0)
    week_count = sum(day["count"] for day in week_days)
    week_skipped = sum(1 for day in week_days if day["skipped"])
    range_skipped = sum(1 for day in days if day["skipped"])
    range_practiced = sum(1 for day in days if day["count"] > 0)

    streak = 0
    cursor = today if today_count else today - timedelta(days=1)
    while cursor >= first_date and counts.get(cursor, 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)

    correct, possible, accuracy_pct = _accuracy(chrono)

    weeks = []
    for i in range(7, -1, -1):
        start = week_start - timedelta(weeks=i)
        end = start + timedelta(days=6)
        total = 0
        day = start
        while day <= end:
            total += counts.get(day, 0)
            day += timedelta(days=1)
        weeks.append({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": f"{MONTHS[start.month - 1]} {start.day}",
            "count": total,
            "current": i == 0,
        })

    by_level = {}
    for row in chrono:
        by_level.setdefault(int(row["level"]), []).append(row)
    levels = []
    for level in sorted(by_level):
        series = sorted(
            by_level[level],
            key=lambda row: (int(row["variant"]), int(row["id"])),
        )
        pace = _pace(series)
        level_correct, level_possible, level_pct = _accuracy(series)
        levels.append({
            "level": level,
            "sessions": len(series),
            "correct": level_correct,
            "possible": level_possible,
            "accuracy_pct": level_pct,
            **pace,
        })

    headline_parts = [
        f"{week_count} sheet{'s' if week_count != 1 else ''} this week"
    ]
    if week_skipped:
        headline_parts.append(
            f"{week_skipped} day{'s' if week_skipped != 1 else ''} skipped"
        )
    elif week_count:
        headline_parts.append("no skipped days")
    if accuracy_pct is not None:
        shown = int(accuracy_pct) if accuracy_pct == int(accuracy_pct) else accuracy_pct
        headline_parts.append(f"{shown}% correct")

    return {
        "has_data": True,
        "session_count": len(chrono),
        "first_date": first_date.isoformat(),
        "today_count": today_count,
        "week_count": week_count,
        "week_skipped": week_skipped,
        "range_skipped": range_skipped,
        "range_practiced": range_practiced,
        "streak": streak,
        "accuracy_pct": accuracy_pct,
        "correct": correct,
        "possible": possible,
        "headline": " · ".join(headline_parts),
        "days": days,
        "week_days": week_days,
        "weeks": weeks,
        "levels": levels,
        "max_day": max((day["count"] for day in days), default=0),
        "max_week": max((week["count"] for week in weeks), default=0),
    }


def format_duration(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(max(0, seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def set_student_options(student_id, options):
    import re
    student = student_by_id(student_id)
    if not student:
        raise ValueError("Choose a student first.")
    allowed = {"show_timing", "themed_sheets", "weekly_reminder", "missed_reminder",
               "notification_consent", "missed_days", "reminder_time"}
    values = {}
    for key, value in options.items():
        if key not in allowed:
            continue
        if key == "missed_days":
            value = int(value)
            if not 1 <= value <= 365:
                raise ValueError("Choose 1–365 days without practice.")
        elif key == "reminder_time":
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(value)):
                raise ValueError("Use a reminder time such as 18:00 (24-hour clock).")
        else:
            if not isinstance(value, bool):
                raise ValueError("Toggle values must be true or false.")
            value = int(value)
        values[key] = value
    consent = values.get("notification_consent", student["notification_consent"])
    if not consent and (values.get("weekly_reminder") or values.get("missed_reminder")):
        raise ValueError("Allow local notifications before enabling reminders.")
    if values.get("notification_consent") == 0:
        values.update(weekly_reminder=0, missed_reminder=0)
    if values:
        assignments = ", ".join(f"{key} = ?" for key in values)
        with session() as conn:
            conn.execute(f"UPDATE students SET {assignments} WHERE id = ?", (*values.values(), student_id))
    return student_by_id(student_id)


def pending_sheets(student_id):
    if not student_id:
        return []
    with session() as conn:
        rows = conn.execute("""
            SELECT sh.* FROM sheets sh
            WHERE sh.student_id = ?
              AND sh.id = (SELECT MAX(s2.id) FROM sheets s2
                           WHERE s2.student_id = sh.student_id AND s2.sheet_code = sh.sheet_code)
              AND NOT EXISTS (SELECT 1 FROM sessions se
                              WHERE se.student_id = sh.student_id AND se.sheet_code = sh.sheet_code)
            ORDER BY sh.level, sh.variant
        """, (student_id,)).fetchall()
    return [dict(row) for row in rows]


def report_weeks(student_id):
    weeks = {}
    for row in list_sessions(student_id) if student_id else []:
        day = _as_date(row["taken_at"])
        monday = day - timedelta(days=day.weekday())
        key = monday.isoformat()
        weeks[key] = weeks.get(key, 0) + 1
    return [{"start": key, "end": (date.fromisoformat(key)+timedelta(days=6)).isoformat(),
             "count": count, "label": f"{key} to {(date.fromisoformat(key)+timedelta(days=6)).isoformat()} · {count} sheets"}
            for key, count in sorted(weeks.items(), reverse=True)]
