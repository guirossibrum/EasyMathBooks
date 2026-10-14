# Easy Math Books

Kumon-style math worksheets for the Omarchy bar. One printable page per sheet,
filled to capacity, plus a matching answer key. Sheet codes are deterministic:
**1-1** is level 1 seed 1, **1-502** is level 1 seed 502. The same code always
reprints the same problems.

| Panel | Sheet 1-1 | Sheet 5-1 |
|:---:|:---:|:---:|
| ![Easy Math Books panel](docs/screenshots/panel.png) | ![Worksheet 1-1](docs/screenshots/worksheet-1-1.png) | ![Worksheet 5-1](docs/screenshots/worksheet-5-1.png) |

Student names, practice times, and filled worksheets stay on this machine.
They are **not** in this repository. The first run creates
`~/.local/share/easymathbooks/easymath.db`.

## Install

```sh
omarchy plugin add https://github.com/guirossibrum/EasyMathBooks.git --enable
```

That clones this repository into `~/.config/omarchy/plugins/grbrum.easymath`
and places the calculator icon on the right of the bar. The first time you
create a worksheet, the plugin installs Python `reportlab` into
`~/.local/share/easymathbooks/venv` (not inside the plugin folder).

Dependencies: Python 3, [reportlab](https://pypi.org/project/reportlab/)
(pulled in automatically on first generate). License: MIT.

## Usage

Click the calculator icon to open the panel. Pick a level and any seed, or
type a sheet code such as `1-502`. Create writes one full page and opens it.
Start the timer when practice begins, enter a score, save the session.

Escape closes the panel. Right-click the icon to print the current sheet.

```sh
omarchy bar move grbrum.easymath --section right
omarchy-shell shell summon grbrum.easymath '{}'
```

CLI from a checkout:

```sh
python generate.py --list
python generate.py --sheet 1-1
python generate.py --sheet 1-502
python generate.py --level 1 --sheets 5
```

## Remove

```sh
omarchy plugin remove grbrum.easymath
```

That removes the bar widget and the cloned plugin folder. It does not delete
`~/.local/share/easymathbooks/` (students and past worksheets). Remove that
directory yourself if you want a clean slate.

## Levels

1-4 single-digit add/subtract · 5-13 multi-digit add/subtract ·
14-18 multiplication · 19-21 division · 22-24 fractions · 25-27 decimals and
percentages · 28-29 negative numbers · 30 order of operations ·
31-32 exponents · 33-35 square/cube roots and radicals ·
36-40 algebra, equations with squares, quadratics.
