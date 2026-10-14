# Easy Math Books contributor guide

## Product

Easy Math Books is a local Omarchy/Quickshell bar plugin for parents. It generates deterministic, printable math worksheets, records practice, and creates personal weekly keepsakes. Favor a short, clear flow and celebrate effort without presenting speed as the measure of success.

The widget has Worksheet and Progress views plus a gear. Every screen must fit without scrolling. Use short subpages, searchable dropdowns, and three-entry pagination for history. The full journal belongs in the external report. Use the Omarchy UI kit and theme tokens.

## Features and contracts

- A sheet code is `level-seed`; the same code and worked-example setting produce the same exercises. There are 40 levels. Paper size and worked examples affect capacity.
- Creation advances the next-print pointer but practice must target the sheet actually generated. Preserve the generated PDF through snapshot refreshes; never open a different sheet's PDF.
- Printed sheets without a matching saved result appear in the unfinished picker. Reprinting preserves their original paper and worked-example settings, regenerates missing PDFs, and does not mark them done. A saved result removes them from that picker.
- Students have names, Male/Female profiles, and three motifs per gender: flowers/unicorns/butterflies or sports/cars/airplanes. Legacy profiles remain unspecified until explicitly saved and use neutral stars. Never imply that an unsaved default is a saved choice.
- Main reports cover the past seven days, including today. The gear offers historical Monday–Sunday weeks with saved results. Do not mix results outside the selected period or include future results.
- Reports emphasize percentage correct and total correct exercises, with a results card for every practiced level. Timing defaults off and must be omitted from both the keepsake and hidden journal when off. Parents can enable it per student.
- Report HTML is self-contained and offline, with vector artwork, print styles, a printable journal, and TV mode. Hide the journal button in TV mode. Keep regular weekly reports printable on one Letter/A4 page; unusually many levels may require additional pages rather than clipping information.
- `encouragement.py` contains 52 original positive messages. The report week's ISO week selects the message consistently; ISO week 53 wraps to the first message.
- Optional themed worksheets reuse the report's vector motifs as stationery. Keep arithmetic legible and preserve the exact exercise plan and problem count. Plain worksheets remain the default.
- Both reminder types default off, independently, for every parent/student. First enable asks permission in the app. Do not infer consent from a conversation or enable reminders during installation.
- Parents type an accepted number of days without recorded practice (1–365) and a local notification time (`HH:MM`, 24-hour clock). These are stored per student. Missed-practice reminders occur at most once per day after the threshold and chosen time. Weekly report reminders occur once per new week, after the chosen time, if the preceding week has results.
- Reminders use Omarchy's notification sender. A one-minute timer in the loaded widget checks due reminders; no systemd service or external scheduler is installed. Persist delivery keys to avoid repeats after reloads or across monitors, and release a key after delivery failure so it can retry.

## Architecture

| File | Responsibility |
|---|---|
| `Panel.qml` | Widget state, bounded views, timer, profile/settings controls, consent dialog, CLI protocol |
| `AppDropdown.qml`, `AppSearchableDropdown.qml` | In-window overlay menus compatible with Omarchy keyboard panels |
| `cli.py` | JSON commands and snapshots; integrates generation, profiles, reports and reminders |
| `store.py` | SQLite records, idempotent migrations, preferences, pending sheets, week index and statistics |
| `generate.py` | Deterministic exercises and PDF layout |
| `worksheet_style.py` | Optional vector motif stationery using ReportLab's SVG path support |
| `report.py`, `report.css` | Offline report documents, selected periods, results cards and print/TV styles |
| `encouragement.py` | Weekly message catalog |
| `reminders.py` | Pure due calculations, deduplication and local notification delivery |
| `bin/easymath-cli` | Python/venv selection and dependency bootstrap |

The base Omarchy `Panel` exposes writable `settings` for shell injection. Do not override it with a read-only property. Snapshot settings live at `snap.settings`. Changes to plugin files may leave cached QML components alive; verify the visible widget after reloading. If needed, use the Omarchy skill and restart the shell rather than claiming a rescan alone proved the new UI is loaded.

## Data and privacy

Real data lives in `${XDG_DATA_HOME:-~/.local/share}/easymathbooks/`, including `easymath.db`, generated worksheets and reports. Keep migrations additive and compatible with older code. Back up the database before testing a new installed version. Normal code rollback must preserve practice recorded during a trial.

Never commit actual student names, records, generated family reports, database backups, or live desktop screenshots. Committed design examples use only the fictional database under `output/ui-review/demo/`. `output/` and database files are Git-ignored.

## Validation

Use the repository venv or a Python environment with `requirements.txt` installed:

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/create_demo.py
.venv/bin/python tools/preview_ui.py
.venv/bin/python tools/render_reports.py
```

Use temporary `XDG_DATA_HOME` values in tests. Test period boundaries, multiple levels, omission of timing, reminder consent/time/threshold/deduplication, and reprinting the original problem count. Inject a fake sender in notification tests; never send real test notifications.

The QML preview checks transitions and that every screen fits. The renderer uses isolated headless Chromium, `pdfinfo`, and `pdftoppm` to produce and validate fake-student PDFs/screenshots. Inspect representative results visually. Desktop cache, keyboard focus, and bar geometry require a live check when installing.

For a user-authorized local installation, follow the Omarchy skill, preserve the complete prior plugin and a consistent database snapshot, and provide a tested rollback script. Do not change the user's reminder preferences during deployment. Do not push or publish changes unless requested.
