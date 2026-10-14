#!/usr/bin/env python3
"""JSON CLI used by the Omarchy EasyMathBooks panel."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from generate import LEVELS, LEVEL_BY_NUM, generate_one, paper_size, preview_sheet, sheet_code
from store import (
    add_session,
    add_student,
    all_settings,
    default_output_dir,
    delete_session,
    delete_student,
    format_duration,
    init_db,
    latest_sheet,
    level_stats,
    list_sessions,
    list_students,
    next_variant,
    progress_report,
    student_progress_pointer,
    record_sheet,
    rename_student,
    set_setting,
    student_by_id,
)


def read_payload(argv):
    if argv:
        return json.loads(argv[0])
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def fail(message, **extra):
    out = {"ok": False, "error": message}
    out.update(extra)
    print(json.dumps(out, ensure_ascii=False))
    return 1


def ok(data=None):
    out = {"ok": True}
    if data:
        out.update(data)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def as_int(value, default=None):
    if value is None or value == "":
        return default
    return int(value)


def as_bool(value, default=False):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def current_settings():
    stored = all_settings()
    paper = stored.get("paper", "letter")
    if paper not in ("letter", "a4"):
        paper = "letter"
    outdir = stored.get("outdir") or str(default_output_dir())
    return {
        "paper": paper,
        "examples": as_bool(stored.get("examples", "1"), True),
        "answers": as_bool(stored.get("answers", "1"), True),
        "outdir": outdir,
        "student_id": as_int(stored.get("student_id")),
        "level": as_int(stored.get("level"), 1),
        "variant": max(1, as_int(stored.get("variant"), 1)),
    }


def persist_selection(payload, settings):
    previous_student = settings["student_id"]
    level = as_int(payload.get("level"), settings["level"])
    variant = max(1, as_int(payload.get("variant"), settings["variant"]))
    student_id = payload.get("student_id", settings["student_id"])
    if "level" in payload:
        set_setting("level", level)
    if "variant" in payload:
        set_setting("variant", variant)
    if "student_id" in payload:
        set_setting("student_id", "" if student_id in (None, "") else int(student_id))
    if "paper" in payload:
        set_setting("paper", payload["paper"])
    if "examples" in payload:
        set_setting("examples", "1" if as_bool(payload["examples"]) else "0")
    if "answers" in payload:
        set_setting("answers", "1" if as_bool(payload["answers"]) else "0")
    if "outdir" in payload:
        set_setting("outdir", payload["outdir"])
    updated = current_settings()
    new_student = updated["student_id"]
    if "student_id" in payload and new_student and new_student != previous_student:
        pointer = student_progress_pointer(new_student)
        set_setting("level", pointer["level"])
        set_setting("variant", pointer["variant"])
        updated = current_settings()
    return updated


def snapshot(settings=None, extra=None):
    settings = settings or current_settings()
    level_num = settings["level"] if settings["level"] in LEVEL_BY_NUM else 1
    variant = max(1, settings["variant"])
    level = LEVEL_BY_NUM[level_num]
    student_id = settings["student_id"]
    students = list_students()
    if student_id and not any(s["id"] == student_id for s in students):
        student_id = None
    last = latest_sheet(sheet_code(level_num, variant), student_id)
    examples = bool(last["examples"]) if last is not None else settings["examples"]
    pagesize = paper_size(settings["paper"])
    preview = preview_sheet(level, variant, pagesize, examples, pages=1)
    problem_count = (
        int(last["problem_count"])
        if last and last.get("problem_count")
        else preview["problem_count"]
    )
    sessions = list_sessions(student_id) if student_id else list_sessions()
    sessions = sorted(
        sessions,
        key=lambda row: (int(row["level"]), int(row["variant"]), int(row["id"])),
    )
    stats = level_stats(student_id) if student_id else []
    report = progress_report(
        student_id,
        today=date.today(),
        sessions=sessions if student_id else [],
    )
    data = {
        "settings": settings,
        "sheet_code": preview["code"],
        "problem_count": problem_count,
        "pages": preview["pages"],
        "levels": [{"num": lv.num, "title": lv.title} for lv in LEVELS],
        "students": students,
        "sessions": sessions[:80],
        "stats": stats,
        "report": report,
        "last_sheet": last,
        "today": date.today().isoformat(),
    }
    if extra:
        data.update(extra)
    return data


def cmd_snapshot(payload):
    settings = persist_selection(payload, current_settings()) if payload else current_settings()
    return ok(snapshot(settings))


def cmd_generate(payload):
    settings = persist_selection(payload, current_settings())
    level = LEVEL_BY_NUM.get(settings["level"])
    if level is None:
        return fail("Unknown level.")
    student_name = None
    student_id = settings["student_id"]
    if student_id:
        student = student_by_id(student_id)
        if student:
            student_name = student["name"]
    result = generate_one(
        level,
        settings["variant"],
        settings["outdir"],
        paper_size(settings["paper"]),
        answers=settings["answers"],
        examples=settings["examples"],
        pages=1,
        student_name=student_name,
    )
    record_sheet(
        result.code,
        result.level,
        result.variant,
        result.problem_count,
        settings["paper"],
        settings["examples"],
        result.pdf_path,
        result.answers_path,
        student_id,
    )
    if student_id:
        set_setting("variant", next_variant(student_id, settings["level"]))
    else:
        set_setting("variant", max(1, settings["variant"]) + 1)
    settings = current_settings()
    return ok(snapshot(settings, {
        "generated": {
            "code": result.code,
            "problem_count": result.problem_count,
            "pdf_path": str(result.pdf_path),
            "answers_path": str(result.answers_path) if result.answers_path else None,
        }
    }))


def cmd_add_student(payload):
    name = str(payload.get("name") or "").strip()
    try:
        student = add_student(name)
    except ValueError as e:
        return fail(str(e))
    except sqlite3.IntegrityError:
        return fail("A student with that name already exists.")
    set_setting("student_id", student["id"])
    return ok(snapshot(current_settings(), {"student": student}))


def cmd_rename_student(payload):
    student_id = as_int(payload.get("student_id"))
    name = str(payload.get("name") or "").strip()
    if not student_id:
        return fail("Pick a student to rename.")
    try:
        rename_student(student_id, name)
    except ValueError as e:
        return fail(str(e))
    except sqlite3.IntegrityError:
        return fail("A student with that name already exists.")
    return ok(snapshot())


def cmd_delete_student(payload):
    student_id = as_int(payload.get("student_id"))
    if not student_id:
        return fail("Pick a student to delete.")
    delete_student(student_id)
    settings = current_settings()
    if settings["student_id"] == student_id:
        set_setting("student_id", "")
    return ok(snapshot(current_settings()))


def cmd_save_session(payload):
    settings = persist_selection(payload, current_settings())
    student_id = settings["student_id"]
    if not student_id:
        return fail("Pick a student before saving a session.")
    seconds = as_int(payload.get("duration_seconds"), 0) or 0
    score = as_int(payload.get("score"))
    score_max = as_int(payload.get("score_max"))
    if score_max is None:
        score_max = as_int(payload.get("problem_count"))
    try:
        row = add_session(
            student_id,
            sheet_code(settings["level"], settings["variant"]),
            settings["level"],
            settings["variant"],
            payload.get("taken_at") or date.today().isoformat(),
            seconds,
            score=score,
            score_max=score_max,
            notes=str(payload.get("notes") or ""),
        )
    except ValueError as e:
        return fail(str(e))
    set_setting("variant", next_variant(student_id, settings["level"]))
    settings = current_settings()
    return ok(snapshot(settings, {"saved": row, "duration_label": format_duration(seconds)}))


def cmd_delete_session(payload):
    session_id = as_int(payload.get("session_id"))
    if not session_id:
        return fail("Missing session.")
    delete_session(session_id)
    return ok(snapshot())


def cmd_next_variant(payload):
    settings = persist_selection(payload, current_settings())
    student_id = settings["student_id"]
    level = settings["level"]
    variant = next_variant(student_id, level) if student_id else settings["variant"] + 1
    set_setting("variant", variant)
    settings = current_settings()
    return ok(snapshot(settings))


COMMANDS = {
    "snapshot": cmd_snapshot,
    "generate": cmd_generate,
    "add-student": cmd_add_student,
    "rename-student": cmd_rename_student,
    "delete-student": cmd_delete_student,
    "save-session": cmd_save_session,
    "delete-session": cmd_delete_session,
    "next-variant": cmd_next_variant,
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    init_db()
    cmd = argv[0] if argv else "snapshot"
    if cmd not in COMMANDS:
        return fail(f"Unknown command {cmd!r}.")
    try:
        payload = read_payload(argv[1:])
        if not isinstance(payload, dict):
            return fail("Payload must be a JSON object.")
        return COMMANDS[cmd](payload)
    except Exception as e:
        return fail(str(e))


if __name__ == "__main__":
    sys.exit(main())
