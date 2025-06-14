import sqlite3

DB_PATH = "/data/users.db"  # путь к базе

day = 4
last_date = '2025-06-14'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("UPDATE users SET day = ?, last_date = ?", (day, last_date))
conn.commit()
conn.close()

print(f"Всем пользователям выставлен day = {day} и last_date = {last_date}")