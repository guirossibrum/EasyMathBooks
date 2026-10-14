# EasyMathBooks

Kumon-style math worksheet generator. One printable page per sheet, filled
to capacity, plus a matching answer key. Sheet codes are deterministic:
**1-1** is level 1 seed 1, **1-502** is level 1 seed 502. The same code
always reprints the same problems.

The app is an Omarchy bar panel (same visual kit as the other plugins).
Python still does generation, students, timing, and progress.

Student names, practice times, and filled worksheets are **local only**.
They are not in this repository. The first time the app runs it creates
an empty database at `~/.local/share/easymathbooks/easymath.db`.

## Setup

    python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    ./easymath

`./easymath` installs the plugin into `~/.config/omarchy/plugins/` and
opens the panel.

## App

- **Sheet** — pick a student, a level, and any seed (no upper bound). Type
  `1-502` in the sheet-code field, or set level 1 and seed 502. Create
  writes one full page and opens it. Start/pause a timer, enter a score,
  save the session.
- **Students** — add and remove names. The selected name is filled on the PDF.
- **Progress** — times, scores, and per-level trend (faster / slower / steady).

## CLI

    .venv/bin/python generate.py --list
    .venv/bin/python generate.py --sheet 1-1
    .venv/bin/python generate.py --sheet 1-502
    .venv/bin/python generate.py --level 1 --sheets 5      # 1-1 through 1-5
    .venv/bin/python generate.py --level 1-10 --start-variant 500 --sheets 3

`--pages` defaults to 1 (maximum problems that fit). Paper: `--paper letter|a4`.

## Levels

1-4 single-digit add/subtract · 5-13 multi-digit add/subtract ·
14-18 multiplication · 19-21 division · 22-24 fractions · 25-27 decimals and
percentages · 28-29 negative numbers · 30 order of operations ·
31-32 exponents · 33-35 square/cube roots and radicals ·
36-40 algebra, equations with squares, quadratics.

Add a level by appending a `Level(...)` to `LEVELS` in `generate.py`.
