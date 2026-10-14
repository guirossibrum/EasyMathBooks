# Easy Math Books contributor guide

## Product

Easy Math Books is a local Omarchy/Quickshell bar plugin for parents. It generates deterministic, printable math worksheets, records practice, and creates personal weekly keepsakes. Favor a short, clear flow and celebrate effort without presenting speed as the measure of success.

The widget has Worksheet and Progress views plus a gear. `currentPage` and `backStack` define navigation; child pages share one persistent Back control. Reprinting belongs to Worksheet, reports and history to Progress, and the gear opens a configuration hub. Profile Save returns to its actual caller. Do not introduce per-page hard-coded return destinations. Every screen must fit without scrolling. Use short subpages, searchable dropdowns, and three-entry pagination for history. The full journal belongs in the external report. Use the Omarchy UI kit and theme tokens.

## Features and contracts

- A sheet code is `level-seed`; the same code and worked-example setting produce the same exercises. There are 40 levels. Paper size and worked examples affect capacity.
- Creation advances the next-print pointer but practice must target the sheet actually generated. Preserve the generated PDF through snapshot refreshes; never open a different sheet's PDF.
- Printed sheets without a matching saved result appear in the unfinished picker. Reprinting preserves their original paper and worked-example settings, regenerates missing PDFs, and does not mark them done. A saved result removes them from that picker.
- Students have names, Male/Female profiles, and three motifs per gender: flowers/unicorns/butterflies or sports/cars/airplanes. Legacy profiles remain unspecified until explicitly saved and use neutral stars. Never imply that an unsaved default is a saved choice.
- Main reports cover the past seven days, including today. Progress offers historical Monday–Sunday weeks with saved results. Do not mix results outside the selected period or include future results.
- Reports emphasize percentage correct and total correct exercises, with a results card for every practiced level. Timing defaults off and must be omitted from both the keepsake and hidden journal when off. Parents can enable it per student.
- Each completed worksheet earns one vector star on its day in the report timeline, across all practiced levels. Days without practice stay quiet. A larger star accompanies the worksheet total; stars count completed sheets, not individual arithmetic problems.
- Report HTML is self-contained and offline, with vector artwork, print styles, a printable journal, and TV mode. Hide the journal button in TV mode. Keep regular weekly reports printable on one Letter/A4 page; unusually many levels may require additional pages rather than clipping information.
- `encouragement.py` contains 52 original positive messages. The report week's ISO week selects the message consistently; ISO week 53 wraps to the first message.
- Optional themed worksheets reuse the report's vector motifs as stationery. Keep arithmetic legible and preserve the exact exercise plan and problem count. Plain worksheets remain the default.
- Both reminder types default off, independently, for every parent/student. First enable asks permission in the app. Do not infer consent from a conversation or enable reminders during installation.
- Parents type an accepted number of days without recorded practice (1–365) and a local notification time (`HH:MM`, 24-hour clock). These are stored per student. Missed-practice reminders occur at most once per day after the threshold and chosen time. Weekly report reminders occur once per new week, after the chosen time, if the preceding week has results.
- Reminders use Omarchy's notification sender. A one-minute timer in the loaded widget checks due reminders; no systemd service or external scheduler is installed. Persist delivery keys to avoid repeats after reloads or across monitors, and release a key after delivery failure so it can retry.

## Architecture

| File | Responsibility |
|---|---|
| `Panel.qml` | Explicit page history, queued subprocess commands, widget state, bounded views, timer, profile/settings controls, consent dialog, CLI protocol |
| `AppDropdown.qml`, `AppSearchableDropdown.qml` | In-window overlay menus compatible with Omarchy keyboard panels |
| `cli.py` | JSON commands and snapshots; integrates generation, profiles, reports and reminders |
| `store.py` | SQLite records, idempotent migrations, preferences, pending sheets, week index and statistics |
| `generate.py` | Deterministic exercises and PDF layout |
| `worksheet_style.py` | Optional vector motif stationery using ReportLab's SVG path support |
| `report.py`, `report.css` | Offline report documents, selected periods, results cards and print/TV styles |
| `encouragement.py` | Weekly message catalog |
| `reminders.py` | Pure due calculations, deduplication and local notification delivery |
| `bin/easymath-cli` | Python/venv selection and dependency bootstrap |

The base Omarchy `Panel` exposes writable `settings` for shell injection. Do not override it with a read-only property. Snapshot settings live at `snap.settings`. The installed plugin is recursively watched: the CLI must use `-B` and `PYTHONDONTWRITEBYTECODE=1` so Python cache writes never reload the widget. Keep reports, databases, and other generated files outside the installed plugin. Publish reports atomically with content-versioned filenames so open documents stay unchanged. Changes to plugin files may leave cached QML components alive; verify the visible widget after reloading. If needed, use the Omarchy skill and restart the shell rather than claiming a rescan alone proved the new UI is loaded.

Dropdowns emit `changed(value)` and let the parent update its state. Never assign their bound `value` internally: that breaks QML bindings and can leave a deleted student's numeric ID on screen. Unknown option values must not be displayed as labels. Runtime checks must select through the actual menu before deleting students, including the last student.

## Data and privacy

Real data lives in `${XDG_DATA_HOME:-~/.local/share}/easymathbooks/`, including `easymath.db`, generated worksheets and reports. Keep migrations additive and compatible with older code. Back up the database before testing a new installed version. Normal code rollback must preserve practice recorded during a trial.

Never commit actual student names, records, generated family reports, database backups, or live desktop screenshots. Public design examples in `docs/showcase/` use only the fictional database under `output/ui-review/demo/`. Keep `docs/ui-review/` and `docs/audit/` as local, Git-ignored review material; do not link to them from public documentation. `output/` and database files are also Git-ignored.

## Validation

Use the repository venv or a Python environment with `requirements.txt` installed:

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/create_demo.py
.venv/bin/python tools/preview_ui.py
.venv/bin/python tools/check_runtime.py
.venv/bin/python tools/check_runtime.py --missing-helper
.venv/bin/python tools/render_reports.py
```

After generating fictional demo reports and widget previews, `tools/render_reports.py --showcase` refreshes the public images/PDFs in `docs/showcase/`. Keep that gallery current with report design changes.

Use temporary `XDG_DATA_HOME` values in tests. Test period boundaries, multiple levels, omission of timing, reminder consent/time/threshold/deduplication, and reprinting the original problem count. Inject a fake sender in notification tests; never send real test notifications.

The QML preview checks transitions and that every screen fits. The renderer uses isolated headless Chromium, `pdfinfo`, and `pdftoppm` to produce and validate fake-student PDFs/screenshots. Inspect representative results visually. Desktop cache, keyboard focus, and bar geometry require a live check when installing.

For a user-authorized local installation, follow the Omarchy skill, preserve the complete prior plugin and a consistent database snapshot, and provide a tested rollback script. Do not change the user's reminder preferences during deployment. Do not push or publish changes unless requested.
