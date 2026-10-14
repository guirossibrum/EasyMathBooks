"""Opt-in local Omarchy notifications. No background services are installed."""
from datetime import datetime, timedelta
import subprocess
from store import list_students, list_sessions, session


def due_reminders(student, sessions, now):
    if not student.get('notification_consent'):
        return []
    if now.strftime('%H:%M') < student.get('reminder_time', '18:00'):
        return []
    today = now.date()
    dated = [r for r in sessions if str(r['taken_at'])[:10] <= today.isoformat()]
    if not dated:
        return []
    due = []
    monday = today - timedelta(days=today.weekday())
    previous = monday - timedelta(days=7)
    if student.get('weekly_reminder') and any(previous.isoformat() <= str(r['taken_at'])[:10] < monday.isoformat() for r in dated):
        due.append(('weekly', monday.isoformat(), 'A week worth keeping',
                    f"{student['name']}'s weekly math report is ready. Open Easy Math Books to print a keepsake."))
    last = max(str(r['taken_at'])[:10] for r in dated)
    gap = (today - datetime.fromisoformat(last).date()).days
    if student.get('missed_reminder') and gap >= int(student.get('missed_days', 3)):
        due.append(('missed', today.isoformat(), 'A little time for math?',
                    f"It has been {gap} days since {student['name']}'s last recorded practice. A small step is a lovely place to restart."))
    return due


def send_notification(title, body):
    subprocess.run(['omarchy-notification-send', '--app-name', 'Easy Math Books',
                    '-g', '󰃬', title, body], check=True, timeout=8,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def check_reminders(now=None, sender=None):
    now = now or datetime.now()
    sender = sender or send_notification
    sent = 0
    for student in list_students():
        if not student.get('notification_consent') or not (student.get('weekly_reminder') or student.get('missed_reminder')):
            continue
        for kind, period, title, body in due_reminders(student, list_sessions(student['id']), now):
            with session() as conn:
                claimed = conn.execute('INSERT OR IGNORE INTO reminder_deliveries VALUES (?, ?, ?)',
                                       (student['id'], kind, period)).rowcount
            if not claimed:
                continue
            try:
                sender(title, body)
            except Exception:
                with session() as conn:
                    conn.execute('DELETE FROM reminder_deliveries WHERE student_id=? AND kind=? AND period=?',
                                 (student['id'], kind, period))
                continue
            sent += 1
    return sent
