"""Self-contained, local family reports for screens and printing."""
from datetime import date, timedelta
from html import escape
from pathlib import Path
import hashlib
import os
import tempfile

from store import default_output_dir, progress_report, format_duration
from encouragement import weekly_message

THEMES = {
    "flowers": ("Garden of growth", "#b64d70", "#f9e5eb", "#fffaf5", "Every little effort helps you bloom."),
    "unicorns": ("A little everyday magic", "#7955b3", "#ede5fb", "#fdfaff", "Wonderful things happen when you keep trying."),
    "butterflies": ("Growing into your wings", "#367c80", "#def2ec", "#fbfcf2", "Look how far your practice has taken you."),
    "sports": ("Your personal best", "#277558", "#e2efe1", "#fffdf4", "Every practice is a step toward your personal best."),
    "cars": ("On the road to great things", "#bd543e", "#ffe6db", "#fffaf4", "Small steps. Steady progress. A wonderful journey."),
    "airplanes": ("Ready for new horizons", "#386eab", "#e0eefb", "#fffdf6", "Your next adventure starts with what you learn today."),
    "stars": ("Little steps, bright futures", "#75614b", "#f2eadb", "#fffdf7", "Every bit of practice is something to be proud of."),
}


def motif_svg(motif):
    """Inline vector artwork stays sharp on paper and needs no network/fonts."""
    drawings = {
        "flowers": '<path d="M140 200Q125 132 157 79M146 160Q92 135 95 112Q138 113 146 160M143 178Q191 143 203 159Q185 189 143 178" fill="none" stroke="#58866a" stroke-width="7"/><g fill="#e99fb4" stroke="#b64d70" stroke-width="2"><ellipse cx="157" cy="55" rx="17" ry="30"/><ellipse cx="157" cy="105" rx="17" ry="30"/><ellipse cx="132" cy="80" rx="30" ry="17"/><ellipse cx="182" cy="80" rx="30" ry="17"/></g><circle cx="157" cy="80" r="17" fill="#f6cf76"/><path d="M64 194V148" stroke="#58866a" stroke-width="5"/><g fill="#edb75f"><circle cx="64" cy="131" r="11"/><circle cx="48" cy="145" r="11"/><circle cx="80" cy="145" r="11"/><circle cx="64" cy="157" r="11"/></g><circle cx="64" cy="145" r="8" fill="#fff7de"/>',
        "unicorns": '<path d="M67 187Q56 127 102 92L114 56L137 82Q163 62 181 90L206 116Q218 139 197 143L172 134L160 192Z" fill="#fff" stroke="#7955b3" stroke-width="4"/><path d="M135 84L150 29L165 84Z" fill="#eac580"/><path d="M101 97Q52 97 56 177L87 202L103 152L118 130" fill="#c9b5e6" stroke="#7955b3" stroke-width="3"/><path d="M114 57L119 88L131 78Z" fill="#eab5ce"/><circle cx="174" cy="105" r="5" fill="#44375b"/><path d="M194 131Q203 131 207 125" fill="none" stroke="#7955b3" stroke-width="3"/>',
        "butterflies": '<path d="M133 126C104 50 44 54 51 110C35 168 89 179 130 139C105 204 163 212 143 138C198 195 235 155 210 116C224 55 165 55 138 125" fill="#a9d7c7" stroke="#367c80" stroke-width="4"/><path d="M132 106L137 164M133 109L120 91M136 109L151 90" stroke="#367c80" stroke-width="6" stroke-linecap="round"/><circle cx="83" cy="111" r="14" fill="#f1cf77"/><circle cx="182" cy="111" r="14" fill="#f1cf77"/>',
        "sports": '<path d="M97 58H184V103Q184 146 141 153Q97 146 97 103Z" fill="#f1c75f" stroke="#a97d28" stroke-width="4"/><path d="M97 70H73V98Q73 121 103 122M185 70H208V98Q208 121 180 122" fill="none" stroke="#a97d28" stroke-width="7"/><path d="M141 153V184M113 192H169" stroke="#a97d28" stroke-width="9" stroke-linecap="round"/><path d="M141 79L147 92L163 94L151 105L154 120L141 112L128 120L131 105L119 94L135 92Z" fill="#fff5ce"/>',
        "cars": '<path d="M43 148L58 111H85L110 77H169L200 112L224 125V167H44Z" fill="#e98d70" stroke="#bd543e" stroke-width="4"/><path d="M99 110L119 86H161L182 110Z" fill="#e5f2f0" stroke="#bd543e" stroke-width="3"/><circle cx="83" cy="165" r="23" fill="#344551"/><circle cx="187" cy="165" r="23" fill="#344551"/><circle cx="83" cy="165" r="10" fill="#fff4e3"/><circle cx="187" cy="165" r="10" fill="#fff4e3"/><path d="M36 200H237" stroke="#c8b69e" stroke-width="3" stroke-dasharray="15 12"/>',
        "airplanes": '<path d="M37 130L112 113L164 52L184 52L157 111L217 106Q239 107 237 122L155 142L127 190L108 190L117 148L66 161Z" fill="#8db8dd" stroke="#386eab" stroke-width="4"/><path d="M65 154L46 174L32 173L39 141" fill="#e8ba70" stroke="#386eab" stroke-width="3"/><path d="M43 74Q63 50 80 72Q106 62 110 85H37Q33 76 43 74M184 184Q199 162 216 180Q238 169 244 193H175Z" fill="#fff" stroke="#bad2e5" stroke-width="2"/>',
        "stars": '<path d="M137 47L157 101L214 104L170 142L183 198L137 167L90 198L103 142L59 104L117 101Z" fill="#eed18a" stroke="#aa8851" stroke-width="4"/>',
    }
    return '<svg class="motif-art" viewBox="0 0 280 240" aria-hidden="true"><circle cx="140" cy="120" r="107" fill="var(--soft)"/>' + drawings.get(motif, drawings["stars"]) + '<g fill="var(--accent)" opacity=".45"><path d="M30 33h12m-6-6v12M237 53h12m-6-6v12M229 211h12m-6-6v12" stroke="currentColor" stroke-width="2"/></g></svg>'


def report_range(period, today, week_start=None):
    if week_start:
        start = date.fromisoformat(week_start)
        if start.weekday() != 0:
            raise ValueError("Archived weeks must start on Monday.")
        return start, start + timedelta(days=6)
    if period not in ("week", "month", "all"):
        raise ValueError("Report period must be week, month, or all.")
    return (today-timedelta(days=6 if period == "week" else 29) if period != "all" else None), today


def achievement_star(extra_class=""):
    """A small vector keeps printed rewards crisp and independent of emoji fonts."""
    return (f'<svg class="achievement-star {extra_class}" viewBox="0 0 32 32" '
            'aria-hidden="true" focusable="false"><path '
            'd="M16 3L19.9 11.3L29 12.5L22.3 18.8L24 28L16 23.5L8 28L9.7 18.8L3 12.5L12.1 11.3Z"/>'
            '</svg>')


def render_report(student, sessions, period="week", today=None, paper="letter", week_start=None, show_timing=None):
    if paper not in ("letter", "a4"):
        raise ValueError("Paper must be letter or a4.")
    today = today or date.today()
    start, end = report_range(period, today, week_start)
    rows = [r for r in sessions if str(r["taken_at"])[:10] <= min(end, today).isoformat()
            and (start is None or str(r["taken_at"])[:10] >= start.isoformat())]
    stats = progress_report(student["id"], today=min(end, today), sessions=rows)
    show_timing = bool(student.get("show_timing", False)) if show_timing is None else bool(show_timing)
    motif = student.get("motif") or "stars"
    title, accent, soft, cream, _ = THEMES.get(motif, THEMES["stars"])
    encouragement = weekly_message(end)
    name = escape(student["name"])
    span = f'{start:%b %d} – {end:%b %d, %Y}' if start else f'All practice · through {end:%b %d, %Y}'
    accuracy = stats.get("accuracy_pct")
    pct = f'{accuracy:g}%' if accuracy is not None else '—'
    problems = sum(int(r.get("score_max") or 0) for r in rows)
    correct = sum(int(r.get("score") or 0) for r in rows)
    count = len(rows)
    active_days = len({str(r["taken_at"])[:10] for r in rows})
    levels = stats.get("levels", [])
    def metric(value, label, detail, reward=False):
        headline = f'<strong>{value}</strong>'
        if reward:
            headline = f'<div class="metric-value">{achievement_star("total-star")}{headline}</div>'
        return f'<div class="metric">{headline}<span>{label}</span><small>{detail}</small></div>'
    metrics = ''.join([metric(count, 'worksheets completed', f'{active_days} '+('day' if active_days == 1 else 'days')+' of practice', reward=True),
                       metric(pct, 'answers correct', f'{problems:,} exercises recorded'),
                       metric(f'{correct:,}', 'correct exercises', f'Across {len(levels)} '+('level' if len(levels) == 1 else 'levels'))])
    calendar_start = start if start and (end-start).days == 6 else end-timedelta(days=6)
    counts = {}
    for r in rows:
        key = str(r['taken_at'])[:10]
        counts[key] = counts.get(key, 0) + 1
    activity = ''
    for offset in range(7):
        day = calendar_start + timedelta(days=offset)
        n = counts.get(day.isoformat(), 0)
        cls = ' practiced' if n else ''
        density = ' many' if n > 6 else ''
        rewards = achievement_star() * n if n else '<i class="rest-mark" aria-hidden="true"></i>'
        description = f'{day:%B} {day.day}: {n} '+('worksheet' if n == 1 else 'worksheets')+' completed'
        activity += (f'<div class="day{cls}" data-date="{day:%Y-%m-%d}" title="{description}">'
                     f'<span>{day:%a}</span><div class="day-stars{density}" role="img" aria-label="{description}">'
                     f'{rewards}</div><small>{day:%b} {day.day}</small></div>')
    from generate import LEVEL_BY_NUM
    level_cards = ''
    detail_levels = ''
    for lv in levels:
        acc = f'{lv["accuracy_pct"]:g}%' if lv['accuracy_pct'] is not None else '—'
        level_name = LEVEL_BY_NUM[lv['level']].title
        timing = ''
        if show_timing:
            bars = ''.join(f'<i style="height:{round(float(p["height"])*100)}%"></i>' for p in lv.get('spark', []))
            timing = f'<div class="level-timing"><p>{escape(lv["pace_label"])}</p><div class="spark">{bars}</div></div>'
        level_cards += f'<div class="level-card"><p class="eyebrow">Level {lv["level"]}</p><h3>{escape(level_name)}</h3><p><strong>{lv["correct"]} correct</strong> of {lv["possible"]} · {acc} accuracy</p>{timing}</div>'
        time_cells = f'<td>{escape(lv["best_pace_label"])}</td><td>{escape(lv["pace_label"])}</td>' if show_timing else ''
        detail_levels += f'<tr><td>Level {lv["level"]}</td><td>{lv["sessions"]}</td><td>{acc}</td>{time_cells}</tr>'
    if level_cards:
        progress_html = f'<section class="level-progress"><div class="section-title"><h2>Every level is part of the journey.</h2></div><div class="level-grid">{level_cards}</div></section>'
    else:
        progress_html = '<div class="pace"><div><p class="eyebrow">A wonderful beginning</p><h3>Ready when you are.</h3><p>The first worksheet starts your story.</p></div></div>'
    session_rows = ''
    for r in sorted(rows, key=lambda x:(str(x['taken_at']),x['id']), reverse=True):
        score = f'{r["score"]} / {r["score_max"]}' if r.get('score') is not None else '—'
        time_cell = f'<td>{format_duration(r["duration_seconds"])}</td>' if show_timing else ''
        session_rows += f'<tr><td>{escape(str(r["taken_at"])[:10])}</td><td>{escape(r["sheet_code"])}</td>{time_cell}<td>{score}</td><td>{escape(r.get("notes") or "")}</td></tr>'
    time_headers = '<th>Best pace</th><th>First → latest pace</th>' if show_timing else ''
    session_time_header = '<th>Time</th>' if show_timing else ''
    details = f'''<section class="details" id="details"><p class="eyebrow">The practice journal</p><h2>Little efforts, recorded.</h2><p class="subtle">{name} · {span}</p>
<h3>Progress by level</h3><table><thead><tr><th>Level</th><th>Sheets</th><th>Accuracy</th>{time_headers}</tr></thead><tbody>{detail_levels or '<tr><td colspan="5">No practice recorded in this period.</td></tr>'}</tbody></table>
<h3>Every practice session</h3><table><thead><tr><th>Date</th><th>Sheet</th>{session_time_header}<th>Correct</th><th>Notes</th></tr></thead><tbody>{session_rows or '<tr><td colspan="5">Your practice journal is ready for its first entry.</td></tr>'}</tbody></table></section>'''
    css = (Path(__file__).with_name("report.css")).read_text()
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} · My math journey</title><style>:root{{--accent:{accent};--soft:{soft};--cream:{cream};}}@page{{size:{'A4' if paper == 'a4' else 'Letter'} portrait;}}{css}</style></head>
<body><nav class="toolbar" aria-label="Report actions"><span>Easy Math Books · Weekly family keepsake</span><div><button onclick="window.print()">Print / save PDF</button><button id="tv" onclick="toggleTV()">TV view</button><button id="journal" onclick="toggleJournal()" aria-expanded="false">Show practice journal</button></div></nav>
<main><article class="keepsake"><div class="topline"><span>EASY MATH BOOKS</span><span>{span}</span></div><header><div><p class="eyebrow">{title}</p><h1>{name}’s<br><em>math journey.</em></h1><p class="intro">A celebration of practice, patience,<br>and all the little steps that add up.</p></div>{motif_svg(motif)}</header>
<div class="metrics">{metrics}</div><section class="activity"><div class="section-title"><h2>A little practice, day by day.</h2><span>{'This week' if week_start else 'Past 7 days'}</span></div><div class="days">{activity}</div><p class="subtle">One star for every worksheet completed. Look at all those little steps.</p></section>{progress_html}
<footer><div class="star">✦</div><div><p>{encouragement}</p><span>We’re proud of the effort you put in, {name}.</span></div><div class="signature">With love,<br><span>________________</span></div></footer><div class="bottomline"><span>A little keepsake. A big reason to be proud.</span><span>Made {today:%B %d, %Y}</span></div></article>{details}</main>
<script>function toggleJournal(){{let open=document.body.classList.toggle('journal-open');document.getElementById('journal').textContent=open?'Hide practice journal':'Show practice journal';document.getElementById('journal').setAttribute('aria-expanded',String(open))}}function toggleTV(){{let active=document.body.classList.toggle('tv');document.getElementById('tv').textContent=active?'Exit TV view':'TV view';if(active&&document.documentElement.requestFullscreen)document.documentElement.requestFullscreen().catch(()=>{{}});else if(!active&&document.fullscreenElement)document.exitFullscreen().catch(()=>{{}})}}if(new URLSearchParams(location.search).has('tv'))document.body.classList.add('tv');document.addEventListener('fullscreenchange',()=>{{if(!document.fullscreenElement){{document.body.classList.remove('tv');document.getElementById('tv').textContent='TV view'}}}})</script></body></html>'''


def write_report(student, sessions, period="week", today=None, paper="letter", week_start=None, show_timing=None):
    today = today or date.today()
    html = render_report(student, sessions, period=period, today=today, paper=paper,
                         week_start=week_start, show_timing=show_timing)
    start, end = report_range(period, today, week_start)
    folder = default_output_dir() / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = folder / f'student-{int(student["id"])}-{start or "all"}-{end}-{digest}.html'
    if not path.exists():
        handle, temporary = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(html)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return path
