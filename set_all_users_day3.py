import sqlite3

DB_PATH = "/data/users.db"  # или измените на свой путь, если БД лежит в другом месте

def set_all_users_day(day_value=3):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET day=? WHERE day != ?", (day_value, day_value))
    conn.commit()
    print(f"Все пользователи теперь на {day_value} дне (без сброса прогресса)")
    conn.close()

if __name__ == "__main__":
    set_all_users_day(3)
