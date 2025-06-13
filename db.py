import sqlite3
from datetime import date, datetime

DB_PATH = "/data/users.db"

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
            day INTEGER DEFAULT 1,
            pushups_today INTEGER DEFAULT 0,
            last_date TEXT,
            fails INTEGER DEFAULT 0,
            completed_time TEXT
        )
    """)
    conn.commit()

def add_user(user_id, name, start_time, end_time, reminders, username=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone():
        return
    cur.execute(
        """
        INSERT INTO users (user_id, username, name, start_time, end_time, reminders, day, pushups_today, last_date, fails, completed_time)
        VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, 0, NULL)
        """,
        (user_id, username, name, start_time, end_time, reminders, date.today().isoformat())
    )
    conn.commit()

def update_user_settings(user_id, start_time, end_time, reminders):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET start_time=?, end_time=?, reminders=? WHERE user_id=?",
        (start_time, end_time, reminders, user_id)
    )
    conn.commit()

def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return dict(row) if row else None

def reset_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()

def add_pushups(user_id, count):
    u = get_user(user_id)
    if not u:
        return False
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if u["last_date"] != today_str:
        pushups = 0
        day = u["day"] + 1
        fails = u["fails"]
        completed_time = None
    else:
        pushups = u["pushups_today"]
        day = u["day"]
        fails = u["fails"]
        completed_time = u.get("completed_time")
    new_pushups = min(pushups + count, 100)
    # Если впервые достигли 100 — зафиксировать время
    if new_pushups >= 100 and not completed_time:
        completed_time = now_str
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=?, last_date=?, day=?, fails=?, completed_time=? WHERE user_id=?",
        (new_pushups, today_str, day, fails, completed_time, user_id)
    )
    conn.commit()
    return True

def decrease_pushups(user_id, count):
    u = get_user(user_id)
    if not u:
        return False
    today_str = date.today().isoformat()
    cur_pushups = u["pushups_today"] if u["last_date"] == today_str else 0
    new_pushups = max(0, cur_pushups - count)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=?, last_date=? WHERE user_id=?",
        (new_pushups, today_str, user_id)
    )
    conn.commit()
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
        "UPDATE users SET day=?, pushups_today=0, last_date=?, fails=?, completed_time=NULL WHERE user_id=?",
        (u["day"] + 1, today_str, u["fails"], user_id)
    )
    conn.commit()

def fail_day(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    fails = min(u["fails"] + 1, 3)
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET fails=?, day=?, pushups_today=0, last_date=?, completed_time=NULL WHERE user_id=?",
        (fails, u["day"] + 1, today_str, user_id)
    )
    conn.commit()
    return fails

def get_fails(user_id):
    u = get_user(user_id)
    return u["fails"] if u else 0

def get_day(user_id):
    u = get_user(user_id)
    return u["day"] if u else 1

def get_all_user_ids():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    return [row["user_id"] for row in cur.fetchall()]

def get_top_pushups_today(limit=5):
    from datetime import date
    conn = get_db()
    cur = conn.cursor()
    today_str = date.today().isoformat()
    cur.execute(
        """
        SELECT username, name, pushups_today, completed_time
        FROM users
        WHERE last_date=?
        ORDER BY
            CASE WHEN pushups_today >= 100 THEN 0 ELSE 1 END,                     -- сначала добившие 100
            CASE WHEN pushups_today >= 100 THEN completed_time END ASC,           -- среди них — кто раньше
            pushups_today DESC                                                    -- остальные по количеству
        LIMIT ?
        """,
        (today_str, limit)
    )
    return cur.fetchall()
