# Easy Math Books — Omarchy plugin

Bar icon that opens the worksheet panel. The generator, student list, and
session log are Python; this folder is only the Omarchy QML shell.

Student names live in the local SQLite database created on first run
(`~/.local/share/easymathbooks/easymath.db`), not in this folder.

From the repo root:

    python -m venv .venv
    .venv/bin/pip install -r requirements.txt
    ./easymath

That copies this plugin into `~/.config/omarchy/plugins/grbrum.easymath`
and puts it on the bar. Click the calculator icon, or run `./easymath`
again to open the panel. Right-click the icon to print the current sheet.
