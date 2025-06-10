import sqlite3
from datetime import datetime

DB_PATH = "devils100.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            start_time TEXT,
            end_time TEXT,
            reminders INTEGER,
            day INTEGER DEFAULT 1,
            pushups_today INTEGER DEFAULT 0,
            fails INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        c.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day INTEGER,
            pushups INTEGER,
            date TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
        ''')
        conn.commit()

def add_user(user_id, username, start_time, end_time, reminders):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, start_time, end_time, reminders, day, pushups_today, fails) VALUES (?, ?, ?, ?, ?, 1, 0, 0)",
                  (user_id, username, start_time, end_time, reminders))
        conn.commit()

def get_user(user_id):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return c.fetchone()

def reset_user(user_id):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()

def add_pushups(user_id, count):
    user = get_user(user_id)
    if not user:
        return False
    pushups_today = user["pushups_today"] + count
    # Убрана проверка на >100 — теперь можно один раз превысить 100!
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET pushups_today=? WHERE user_id=?", (pushups_today, user_id))
        conn.commit()
    return True

def get_pushups_today(user_id):
    user = get_user(user_id)
    return user["pushups_today"] if user else 0

def next_day(user_id):
    user = get_user(user_id)
    if not user:
        return
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO progress (user_id, day, pushups, date) VALUES (?, ?, ?, ?)",
                  (user_id, user["day"], user["pushups_today"], datetime.utcnow().isoformat()))
        c.execute("UPDATE users SET day=day+1, pushups_today=0 WHERE user_id=?", (user_id,))
        conn.commit()

def fail_day(user_id):
    user = get_user(user_id)
    if user:
        fails = user["fails"] + 1
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET fails=?, pushups_today=0, day=day+1 WHERE user_id=?", (fails, user_id))
            c.execute("INSERT INTO progress (user_id, day, pushups, date) VALUES (?, ?, ?, ?)",
                      (user_id, user["day"], user["pushups_today"], datetime.utcnow().isoformat()))
            conn.commit()
        return fails

def get_fails(user_id):
    user = get_user(user_id)
    return user["fails"] if user else 0

def get_day(user_id):
    user = get_user(user_id)
    return user["day"] if user else 1

def get_all_user_ids():
    """Получить список всех user_id из таблицы users (для запуска напоминалок при старте бота)."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row["user_id"] for row in c.fetchall()]
