#!/usr/bin/env python3
"""Create a reusable, entirely fictional database and six family report samples."""
from datetime import date, timedelta
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEMO_HOME = ROOT / 'output/ui-review/demo'
os.environ['XDG_DATA_HOME'] = str(DEMO_HOME)
import store
from report import render_report
from generate import generate_one, LEVEL_BY_NUM, paper_size
import shutil


def main():
    store.init_db()
    today = date(2026, 10, 13)
    students = [('Lily', 'female', 'flowers'), ('Mia', 'female', 'unicorns'),
                ('Sophie', 'female', 'butterflies'), ('Noah', 'male', 'sports'),
                ('Leo', 'male', 'cars'), ('Oliver', 'male', 'airplanes')]
    rng = random.Random(42)
    out = ROOT / 'docs/ui-review'
    out.mkdir(parents=True, exist_ok=True)
    existing = {s['name']: s for s in store.list_students()}
    for index, (name, gender, motif) in enumerate(students):
        student = existing.get(name) or store.add_student(name, gender, motif)
        if not store.list_sessions(student['id']):
            variant = {1: 0, 2: 0, 3: 0}
            for day in range(45):
                if rng.random() < .16:
                    continue
                level = min(3, day // 17 + 1)
                variant[level] += 1
                seconds = max(65, 230 - variant[level]*7 + rng.randint(-10, 10))
                correct = min(25, 19+variant[level]//2+rng.randint(0, 2))
                store.add_session(student['id'], f'{level}-{variant[level]}', level,
                                  variant[level], (today-timedelta(days=44-day)).isoformat(),
                                  seconds, score=correct, score_max=25,
                                  notes='Kept trying and finished independently.' if day == 44 else '')
        sessions = store.list_sessions(student['id'])
        if not any(r['sheet_code'] == '2-90' for r in sessions):
            store.add_session(student['id'], '2-90', 2, 90, '2026-10-10', 125,
                              score=25, score_max=25, notes='A little review of an earlier level.')
        sessions = store.list_sessions(student['id'])
        worksheet = generate_one(LEVEL_BY_NUM[2], 99, ROOT/'output/ui-review/sheets',
                                 paper_size('letter'), examples=False, student_name=name, motif=motif)
        shutil.copy2(worksheet.pdf_path, out/f'worksheet-{motif}.pdf')
        if not store.latest_sheet('2-99', student['id']):
            store.record_sheet('2-99', 2, 99, worksheet.problem_count, 'letter', False,
                               worksheet.pdf_path, worksheet.answers_path, student['id'])
        html = render_report(student, sessions, today=today)
        (out / f'report-{motif}.html').write_text(html, encoding='utf-8')
        if motif == 'flowers':
            (out/'report-flowers-timed.html').write_text(render_report(student, sessions, today=today, show_timing=True), encoding='utf-8')
            (out/'report-flowers-archived.html').write_text(render_report(student, sessions, today=today, week_start='2026-10-05'), encoding='utf-8')
    store.set_setting('student_id', 1)
    store.set_setting('level', 1)
    store.set_setting('variant', 15)
    print(f'Fake database: {store.db_path()}')
    print(f'Six self-contained report samples: {out}')


if __name__ == '__main__':
    main()
