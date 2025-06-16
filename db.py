import sqlite3
from datetime import date, datetime
from pytz import timezone

DB_PATH = "/data/users.db"

KIEV_TZ = timezone("Europe/Kyiv")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            start_time TEXT,
            end_time TEXT,
            reminders INTEGER,
            pushups_today INTEGER DEFAULT 0,
            last_date TEXT,
            fails INTEGER DEFAULT 0,
            completed_time TEXT,
            registered_date TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, name, start_time, end_time, reminders, username=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone():
        conn.close()
        return
    today_str = date.today().isoformat()
    cur.execute(
        """
        INSERT INTO users (user_id, username, name, start_time, end_time, reminders, pushups_today, last_date, fails, completed_time, registered_date)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, NULL, ?)
        """,
        (user_id, username, name, start_time, end_time, reminders, today_str, today_str)
    )
    conn.commit()
    conn.close()

def update_user_settings(user_id, start_time, end_time, reminders):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET start_time=?, end_time=?, reminders=? WHERE user_id=?",
        (start_time, end_time, reminders, user_id)
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def reset_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    # Удаляем пользователя полностью, чтобы при повторной регистрации дата регистрации сбросилась
    cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def add_pushups(user_id, count):
    u = get_user(user_id)
    if not u:
        return False
    today_str = date.today().isoformat()
    now_str = datetime.now(KIEV_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if u["last_date"] != today_str:
        pushups = 0
        fails = u["fails"]
        completed_time = None
    else:
        pushups = u["pushups_today"]
        fails = u["fails"]
        completed_time = u.get("completed_time")
    new_pushups = min(pushups + count, 100)
    # Если впервые достигли 100 — зафиксировать время
    if new_pushups >= 100 and not completed_time:
        completed_time = now_str
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=?, last_date=?, fails=?, completed_time=? WHERE user_id=?",
        (new_pushups, today_str, fails, completed_time, user_id)
    )
    conn.commit()
    conn.close()
    return True

def decrease_pushups(user_id, count):
    u = get_user(user_id)
    if not u:
        return False
    today_str = date.today().isoformat()
    cur_pushups = u["pushups_today"] if u["last_date"] == today_str else 0
    new_pushups = max(0, cur_pushups - count)
    completed_time = u["completed_time"]
    # Если было >=100, а стало <100 — сбросить completed_time
    if cur_pushups >= 100 and new_pushups < 100:
        completed_time = None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=?, last_date=?, completed_time=? WHERE user_id=?",
        (new_pushups, today_str, completed_time, user_id)
    )
    conn.commit()
    conn.close()
    return new_pushups

def get_pushups_today(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    today_str = date.today().isoformat()
    if u["last_date"] != today_str:
        return 0
    return u["pushups_today"]

def next_day(user_id):
    u = get_user(user_id)
    if not u:
        return
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=0, last_date=?, fails=?, completed_time=NULL WHERE user_id=?",
        (today_str, u["fails"], user_id)
    )
    conn.commit()
    conn.close()

def fail_day(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    fails = min(u["fails"] + 1, 3)
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET fails=?, pushups_today=0, last_date=?, completed_time=NULL WHERE user_id=?",
        (fails, today_str, user_id)
    )
    conn.commit()
    conn.close()
    return fails

def get_fails(user_id):
    u = get_user(user_id)
    return u["fails"] if u else 0

def get_user_current_day(u):
    """
    Возвращает текущий день челленджа для пользователя u (dict).
    """
    today = date.today()
    reg_date = datetime.strptime(u["registered_date"], "%Y-%m-%d").date()
    return (today - reg_date).days + 1

def get_all_user_ids():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    ids = [row["user_id"] for row in cur.fetchall()]
    conn.close()
    return ids

def get_top_pushups_today(limit=5):
    conn = get_db()
    cur = conn.cursor()
    today_str = date.today().isoformat()
    cur.execute(
        """
        SELECT * FROM users
        WHERE last_date=?
        ORDER BY
            CASE WHEN pushups_today >= 100 THEN 0 ELSE 1 END,
            CASE WHEN pushups_today >= 100 THEN completed_time END ASC,
            pushups_today DESC
        LIMIT ?
        """,
        (today_str, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return rows
