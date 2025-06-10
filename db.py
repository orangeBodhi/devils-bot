import sqlite3
from datetime import date

DB_PATH = "users.db"

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
            fails INTEGER DEFAULT 0
        )
    """)
    conn.commit()

def add_user(user_id, name, start_time, end_time, reminders, username=None):
    """
    Создать нового пользователя. Если пользователь уже есть — ничего не делать.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone():
        # Пользователь уже есть, не трогать!
        return
    cur.execute(
        """
        INSERT INTO users (user_id, username, name, start_time, end_time, reminders, day, pushups_today, last_date, fails)
        VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, 0)
        """,
        (user_id, username, name, start_time, end_time, reminders, date.today().isoformat())
    )
    conn.commit()

def update_user_settings(user_id, start_time, end_time, reminders):
    """
    Обновить только настройки пользователя, не трогая прогресс, день и жизни.
    """
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
    """
    Полный сброс пользователя (как новая регистрация)
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()

def add_pushups(user_id, count):
    """
    Добавляет count отжиманий к сегодняшним, максимум 100.
    """
    u = get_user(user_id)
    if not u:
        return False
    today_str = date.today().isoformat()
    if u["last_date"] != today_str:
        # Новый день — сбросить прогресс дня, увеличить day на 1
        pushups = 0
        day = u["day"] + 1
        fails = u["fails"]  # Не сбрасываем жизни
    else:
        pushups = u["pushups_today"]
        day = u["day"]
        fails = u["fails"]
    new_pushups = min(pushups + count, 100)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET pushups_today=?, last_date=?, day=?, fails=? WHERE user_id=?",
        (new_pushups, today_str, day, fails, user_id)
    )
    conn.commit()
    return True

def get_pushups_today(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    today_str = date.today().isoformat()
    if u["last_date"] != today_str:
        return 0
    return u["pushups_today"]

def next_day(user_id):
    """
    Переключить пользователя на следующий день и обнулить прогресс дня
    """
    u = get_user(user_id)
    if not u:
        return
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET day=?, pushups_today=0, last_date=?, fails=? WHERE user_id=?",
        (u["day"] + 1, today_str, u["fails"], user_id)
    )
    conn.commit()

def fail_day(user_id):
    """
    Добавить фейл (минус жизнь) и перейти на следующий день
    Возвращает новое число fails
    """
    u = get_user(user_id)
    if not u:
        return 0
    fails = min(u["fails"] + 1, 3)
    today_str = date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET fails=?, day=?, pushups_today=0, last_date=? WHERE user_id=?",
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
