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
            registered_date TEXT,
            notify_fail INTEGER DEFAULT 0,
            game_over INTEGER DEFAULT 0
        )
    """)
    # Миграция для старых БД: notify_fail
    cur.execute("PRAGMA table_info(users);")
    cols = [row[1] for row in cur.fetchall()]
    if "notify_fail" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN notify_fail INTEGER DEFAULT 0;")
            conn.commit()
        except Exception as e:
            print("Failed to add notify_fail:", e)
    if "game_over" not in cols:
        try:
            cur.execute("ALTER TABLE users ADD COLUMN game_over INTEGER DEFAULT 0;")
            conn.commit()
        except Exception as e:
            print("Failed to add game_over:", e)
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
        INSERT INTO users (user_id, username, name, start_time, end_time, reminders, pushups_today, last_date, fails, completed_time, registered_date, notify_fail, game_over)
        VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, NULL, ?, 0, 0)
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
    cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def add_pushups(user_id, count):
    u = get_user(user_id)
    if not u or u.get("game_over", 0):
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
    if not u or u.get("game_over", 0):
        return False
    today_str = date.today().isoformat()
    cur_pushups = u["pushups_today"] if u["last_date"] == today_str else 0
    new_pushups = max(0, cur_pushups - count)
    completed_time = u["completed_time"]
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
    if not u or u.get("game_over", 0):
        return 0
    today_str = date.today().isoformat()
    if u["last_date"] != today_str:
        return 0
    return u["pushups_today"]

def next_day(user_id):
    u = get_user(user_id)
    if not u or u.get("game_over", 0):
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
    if not u or u.get("game_over", 0):
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
    return u["fails"] if u and not u.get("game_over", 0) else 0

def get_user_current_day(u):
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
        WHERE last_date=? AND game_over=0
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

def get_notify_fail(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT notify_fail FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row["notify_fail"] if row else 0

def set_notify_fail(user_id, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET notify_fail=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def get_game_over(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT game_over FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row["game_over"] if row else 0

def set_game_over(user_id, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET game_over=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()
