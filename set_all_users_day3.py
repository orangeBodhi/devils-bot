import sqlite3

DB_PATH = "/data/users.db"

def set_day_all(day=3):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET day = ?", (day,))
    conn.commit()
    conn.close()
    print(f"Все пользователи теперь на дне {day}!")

if __name__ == "__main__":
    set_day_all(3)